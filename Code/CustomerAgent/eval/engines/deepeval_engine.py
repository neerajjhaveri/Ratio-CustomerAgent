"""
DeepEval Engine - RatioAI DeepEval Integration
=============================================

This module provides a complete DeepEval implementation following the RatioAI
evaluation framework interface. It handles Azure OpenAI integration, 
Confident AI cloud streaming, and various evaluation metrics.

Features:
- Azure OpenAI integration with token caching
- Confident AI cloud streaming
- Multiple evaluation metrics (Hallucination, Faithfulness, etc.)
- Custom PII Detection metric
- Performance monitoring and logging
"""

import json
import os
import logging
import time
import deepeval
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI, AsyncAzureOpenAI

from deepeval import evaluate
from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval.metrics import (
    HallucinationMetric,
    FaithfulnessMetric,
    AnswerRelevancyMetric,
    ToxicityMetric,
    ContextualPrecisionMetric,
    SummarizationMetric
)

# Import the base interfaces
from Code.Shared.evaluation.interfaces import BaseEvaluator, EvaluationResult, EvaluationInput, EvaluationStatus

# Configure logging
log_file = os.path.join(os.path.dirname(__file__), "deepeval_engine.log")
logging.basicConfig(level=logging.INFO, filename=log_file, filemode="a", 
                   format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Configuration files
TESTCASE_FILE = os.path.join(os.path.dirname(__file__), "testcases.json")
TOKEN_CACHE_FILE = os.path.join(os.path.dirname(__file__), "token_cache.json")

# DeepEval supported metrics
DEEPEVAL_METRICS = [
    "Hallucination",
    "Faithfulness", 
    "Answer Relevancy",
    "Toxicity",
    "Contextual Precision",
    "Summarization",
    "PII Detection"
]

class ConfidentAIIntegration:
    """Handles Confident AI cloud streaming integration"""
    
    def __init__(self):
        self.enabled = self._initialize()
    
    def _initialize(self) -> bool:
        """Initialize DeepEval with Confident AI credentials"""
        try:
            # Check for Confident AI API key in environment
            confident_api_key = (os.getenv('DEEPEVAL') or 
                               os.getenv('DEEPEVAL2') or 
                               os.getenv('CONFIDENT_API_KEY'))
            
            if confident_api_key:
                logger.info("Configuring DeepEval with Confident AI credentials")
                # Set the API key for DeepEval
                os.environ['DEEPEVAL_API_KEY'] = confident_api_key
                
                # Login to Confident AI (this enables cloud streaming)
                deepeval.login_with_confident_api_key(confident_api_key)
                logger.info("✅ Successfully logged into Confident AI")
                return True
            else:
                logger.warning("No Confident AI API key found. Results will only be stored locally.")
                return False
        except Exception as e:
            logger.error(f"Error initializing Confident AI: {e}")
            return False

class AzureClientManager:
    """Manages Azure OpenAI clients with token caching"""
    
    def __init__(self):
        self._azure_client = None
        self._async_azure_client = None
        self._token_provider = None
        self._initialized_endpoint = None
        self._initialized_deployment = None
    
    def load_token_cache(self):
        """Load cached Azure AD token"""
        try:
            with open(TOKEN_CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
                expiry = datetime.fromisoformat(cache['expiry'])
                if datetime.now() < expiry:
                    return cache['token'], expiry
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass
        return None, None

    def save_token_cache(self, token, expiry):
        """Save Azure AD token to cache"""
        cache = {"token": token, "expiry": expiry.isoformat()}
        with open(TOKEN_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False)

    def initialize_clients(self, azure_endpoint: str, azure_deployment: str, 
                         api_version: str = "2024-04-01-preview"):
        """Initialize Azure OpenAI clients"""
        start_time = time.perf_counter()
        
        if (self._azure_client is None or self._async_azure_client is None or 
            self._initialized_endpoint != azure_endpoint or 
            self._initialized_deployment != azure_deployment):
            
            if not azure_endpoint or not azure_deployment:
                raise ValueError("azure_endpoint and azure_deployment must be provided")

            logger.info("Starting Azure client initialization")
            
            # Handle token caching
            token, token_expiry = self.load_token_cache()
            if token and token_expiry and datetime.now() < token_expiry:
                logger.info("Reusing cached Azure AD token")
            else:
                logger.info("Acquiring new Azure AD token")
                credential = DefaultAzureCredential()
                token_response = credential.get_token("https://cognitiveservices.azure.com/.default")
                token = token_response.token
                token_expiry = datetime.fromtimestamp(token_response.expires_on - 300)  # Buffer 5 minutes
                self.save_token_cache(token, token_expiry)
                logger.info(f"New token acquired, expires at {token_expiry}")
            
            os.environ["AZURE_OPENAI_AD_TOKEN"] = token
            os.environ["OPENAI_API_VERSION"] = api_version

            # Initialize token provider and clients
            credential = DefaultAzureCredential()
            self._token_provider = get_bearer_token_provider(
                credential, "https://cognitiveservices.azure.com/.default"
            )

            self._azure_client = AzureOpenAI(
                api_version=api_version,
                azure_endpoint=azure_endpoint,
                azure_deployment=azure_deployment,
                azure_ad_token_provider=self._token_provider
            )

            self._async_azure_client = AsyncAzureOpenAI(
                api_version=api_version,
                azure_endpoint=azure_endpoint,
                azure_deployment=azure_deployment,
                azure_ad_token_provider=self._token_provider
            )

            self._initialized_endpoint = azure_endpoint
            self._initialized_deployment = azure_deployment
            
            end_time = time.perf_counter()
            logger.info(f"Azure clients initialized in {end_time - start_time:.2f} seconds")

    def get_clients(self):
        """Get the initialized Azure clients"""
        return self._azure_client, self._async_azure_client

class PIIDetectionMetric(BaseMetric):
    """Custom PII Detection metric for DeepEval"""
    
    def __init__(self, threshold: float = 0.5, model=None):
        self.threshold = threshold
        self.model = model
        if not model:
            raise ValueError("Model must be provided for PII Detection metric")

    async def a_measure(self, test_case: LLMTestCase):
        try:
            output = test_case.actual_output
            prompt = (
                f"Analyze the following text for Personally Identifiable Information (PII), including Names (e.g., John Doe), "
                f"Emails (e.g., user@example.com), Addresses (e.g., 123 Main St, City, State ZIP), and IP Addresses "
                f"(e.g., 192.168.1.1 or 2001:db8::1). Return a JSON object with a 'detected_pii' list of PII types found "
                f"(e.g., ['Name', 'Email']) and a 'reason' explaining the findings. If no PII is found, return an empty "
                f"'detected_pii' list and a reason. Text: {output}"
            )
            
            response = await self.model.a_generate(prompt)
            try:
                result = json.loads(response)
                detected_pii = result.get('detected_pii', [])
                reason = result.get('reason', 'No reason provided')
            except json.JSONDecodeError:
                raise ValueError(f"Failed to parse PII detection response: {response}")

            if detected_pii:
                self.success = False
                self.score = 0.0
                self.reason = f"PII detected: {', '.join(detected_pii)}. {reason}"
            else:
                self.success = True
                self.score = 1.0
                self.reason = reason or "No PII detected in the output."

            return self.score
        except Exception as e:
            self.success = False
            self.score = 0.0
            self.reason = f"Error in PII detection: {str(e)}"
            return self.score

    def measure(self, test_case: LLMTestCase):
        import asyncio
        return asyncio.run(self.a_measure(test_case))

    def is_successful(self):
        return self.success

    @property
    def __name__(self):
        return "PII Detection"

class CustomAzureOpenAIModel(DeepEvalBaseLLM):
    """Custom Azure OpenAI model wrapper for DeepEval"""
    
    def __init__(self, model: str = None, azure_endpoint: str = None, 
                 azure_deployment: str = None, api_version: str = "2025-04-01-preview"):
        init_start = time.perf_counter()
        self.model_name = model or "gpt-4.1"
        self.azure_endpoint = azure_endpoint
        self.azure_deployment = azure_deployment
        self.api_version = api_version
        
        # Initialize Azure clients
        self.client_manager = AzureClientManager()
        self.client_manager.initialize_clients(azure_endpoint, azure_deployment, api_version)
        self.client, self.async_client = self.client_manager.get_clients()
        
        super().__init__(model_name=self.model_name)
        init_end = time.perf_counter()
        logger.info(f"CustomAzureOpenAIModel __init__ took {init_end - init_start:.2f} seconds")

    def load_model(self, async_mode: bool = False):
        return self.async_client if async_mode else self.client

    async def generate(self, prompt: str) -> str:
        start_time = time.perf_counter()
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        result = response.choices[0].message.content
        result = result.encode('ascii', 'ignore').decode('ascii')
        logger.info(f"Azure response: {result}")
        end_time = time.perf_counter()
        logger.info(f"generate took {end_time - start_time:.2f} seconds")
        return result

    async def a_generate(self, prompt: str, schema: object = None) -> object:
        start_time = time.perf_counter()
        
        kwargs = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": f"{prompt}\n\nPlease provide the response in JSON format."}],
            "response_format": {"type": "json_object"}
        }
        
        response = await self.async_client.chat.completions.create(**kwargs)
        response_content = response.choices[0].message.content
        response_content = response_content.encode('ascii', 'ignore').decode('ascii')
        logger.info(f"Azure async response: {response_content}")
        
        if schema and hasattr(schema, "schema"):
            try:
                json_response = json.loads(response_content)
                model_instance = schema(**json_response)
                return model_instance
            except (json.JSONDecodeError, ValueError) as e:
                raise ValueError(f"Failed to parse response as pydantic model: {e}\nResponse: {response_content}")
        
        end_time = time.perf_counter()
        logger.info(f"a_generate took {end_time - start_time:.2f} seconds")
        return response_content

    def get_model_name(self):
        return self.model_name

class DeepEvalEngine(BaseEvaluator):
    """DeepEval implementation of the RatioAI evaluation framework"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.version = "1.0.0"
        self.confident_ai = ConfidentAIIntegration()
        logger.info(f"DeepEval Engine initialized. Confident AI enabled: {self.confident_ai.enabled}")
    
    def get_available_metrics(self) -> List[str]:
        """Return list of available DeepEval metrics"""
        return DEEPEVAL_METRICS.copy()
    
    def configure_metric(self, metric_name: str, threshold: float, **kwargs) -> bool:
        """Configure a specific DeepEval metric"""
        if metric_name not in DEEPEVAL_METRICS:
            logger.error(f"Invalid metric: {metric_name}. Available: {DEEPEVAL_METRICS}")
            return False
        
        logger.info(f"Configured metric {metric_name} with threshold {threshold}")
        return True
    
    def supports_cloud_streaming(self) -> bool:
        """Check if Confident AI cloud streaming is available"""
        return self.confident_ai.enabled
    
    def _create_deepeval_metric(self, metric_name: str, threshold: float, model):
        """Create a DeepEval metric instance"""
        if metric_name == "Hallucination":
            return HallucinationMetric(threshold=threshold, model=model)
        elif metric_name == "Faithfulness":
            return FaithfulnessMetric(threshold=threshold, model=model)
        elif metric_name == "Answer Relevancy":
            return AnswerRelevancyMetric(threshold=threshold, model=model)
        elif metric_name == "Toxicity":
            return ToxicityMetric(threshold=threshold, model=model)
        elif metric_name == "Contextual Precision":
            return ContextualPrecisionMetric(threshold=threshold, model=model)
        elif metric_name == "Summarization":
            return SummarizationMetric(threshold=threshold, model=model)
        elif metric_name == "PII Detection":
            return PIIDetectionMetric(threshold=threshold, model=model)
        else:
            raise ValueError(f"Unsupported metric: {metric_name}")
    
    def run_evaluation(
        self, 
        evaluation_input: EvaluationInput,
        selected_metrics: Dict[str, float],
        azure_endpoint: str = None,
        azure_deployment: str = None,
        experiment_name: str = None,
        dataset_name: str = None,
        send_to_confident: bool = True,
        **kwargs
    ) -> List[EvaluationResult]:
        """Run DeepEval evaluation and return standardized results"""
        start_time = time.perf_counter()
        logger.info("Starting DeepEval evaluation")
        
        results = []
        
        # Initialize Azure model
        model = CustomAzureOpenAIModel(
            azure_endpoint=azure_endpoint, 
            azure_deployment=azure_deployment
        )
        
        # Create DeepEval test case
        deepeval_test = LLMTestCase(
            input=evaluation_input.input_text,
            actual_output=evaluation_input.actual_output,
            context=evaluation_input.context if evaluation_input.context else [],
            retrieval_context=evaluation_input.context if evaluation_input.context else [],
            expected_output=evaluation_input.expected_output or evaluation_input.actual_output
        )
        
        # Add metadata for Confident AI
        if self.confident_ai.enabled and send_to_confident:
            if experiment_name:
                deepeval_test.name = f"{experiment_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            deepeval_test.additional_metadata = {
                "experiment": experiment_name or f"RatioAI_Eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "dataset": dataset_name or "RatioAI_Dataset", 
                "azure_endpoint": azure_endpoint,
                "azure_deployment": azure_deployment,
                "timestamp": datetime.now().isoformat(),
                "selected_metrics": list(selected_metrics.keys())
            }
        
        # Create metrics
        metrics = []
        for metric_name, threshold in selected_metrics.items():
            try:
                metric = self._create_deepeval_metric(metric_name, threshold, model)
                metrics.append(metric)
            except Exception as e:
                logger.error(f"Error creating metric {metric_name}: {e}")
                results.append(EvaluationResult(
                    metric_name=metric_name,
                    score=None,
                    threshold=threshold,
                    status=EvaluationStatus.ERROR,
                    success=False,
                    error=f"Metric initialization failed: {str(e)}"
                ))
        
        # Run evaluation
        if metrics:
            try:
                if self.confident_ai.enabled and send_to_confident:
                    logger.info("Running evaluation with Confident AI cloud streaming")
                else:
                    logger.info("Running evaluation locally")
                
                eval_result = evaluate([deepeval_test], metrics)
                
                # Process results
                if hasattr(eval_result, 'test_results') and len(eval_result.test_results) > 0:
                    test_result = eval_result.test_results[0]
                    if hasattr(test_result, 'metrics_data') and len(test_result.metrics_data) > 0:
                        for metric_data in test_result.metrics_data:
                            score = getattr(metric_data, 'score', None)
                            success = getattr(metric_data, 'success', False)
                            
                            # Determine status
                            if score is None:
                                status = EvaluationStatus.ERROR
                            elif success:
                                status = EvaluationStatus.PASS
                            else:
                                status = EvaluationStatus.FAIL
                            
                            # Create result with metadata
                            metadata = {}
                            if self.confident_ai.enabled and send_to_confident:
                                metadata.update({
                                    "confident_ai_streamed": True,
                                    "experiment_name": experiment_name,
                                    "dataset_name": dataset_name
                                })
                            
                            result = EvaluationResult(
                                metric_name=metric_data.name,
                                score=score,
                                threshold=getattr(metric_data, 'threshold', None),
                                status=status,
                                success=success,
                                reason=getattr(metric_data, 'reason', None),
                                metadata=metadata
                            )
                            results.append(result)
                            
            except Exception as e:
                logger.error(f"Error during evaluation: {e}")
                for metric_name in selected_metrics.keys():
                    results.append(EvaluationResult(
                        metric_name=metric_name,
                        score=None,
                        threshold=selected_metrics[metric_name],
                        status=EvaluationStatus.ERROR,
                        success=False,
                        error=str(e)
                    ))
        
        end_time = time.perf_counter()
        logger.info(f"DeepEval evaluation completed in {end_time - start_time:.2f} seconds")
        return results