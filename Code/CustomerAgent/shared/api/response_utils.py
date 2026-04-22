"""
FastAPI response utilities for consistent API responses across RatioAI services

This module provides standardized response formatting for:
- Success responses with data payload
- Error responses with proper HTTP status codes
- Evaluation-specific response formats
- Logging integration for API operations

Usage:
    from Code.Shared.api.response_utils import create_success_response, create_error_response
    
    # Success response
    return create_success_response(data=results, message="Evaluation completed")
    
    # Error response  
    raise create_error_response("Invalid request", 400)
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import HTTPException

# Configure logger
logger = logging.getLogger(__name__)


def create_success_response(
    data: Any, 
    message: str = "Success",
    meta: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create standardized success response for API endpoints.
    
    Args:
        data: Response data payload
        message: Success message description
        meta: Optional metadata (pagination, timestamps, etc.)
        
    Returns:
        Standardized success response dictionary
    """
    response = {
        "status": "success",
        "message": message,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    if meta:
        response["meta"] = meta
        
    logger.info("API Success: %s", message)
    return response


def create_error_response(
    error: str, 
    code: int = 400,
    details: Optional[Dict[str, Any]] = None
) -> HTTPException:
    """
    Create standardized error response for API endpoints.
    
    Args:
        error: Error message description
        code: HTTP status code
        details: Optional error details dictionary
        
    Returns:
        HTTPException with standardized error format
    """
    error_detail: Dict[str, Any] = {
        "status": "error", 
        "message": error,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    if details:
        error_detail["details"] = details
        
    logger.error("API Error %d: %s", code, error)
    
    if details:
        logger.error("Error details: %s", details)
    
    raise HTTPException(status_code=code, detail=error_detail)


def create_evaluation_response(
    results: List[Any], 
    metrics_count: int,
    experiment_name: Optional[str] = None,
    dataset_name: Optional[str] = None,
    confident_ai_streamed: bool = False
) -> Dict[str, Any]:
    """
    Create standardized evaluation response format.
    
    Args:
        results: List of evaluation results
        metrics_count: Number of metrics evaluated
        experiment_name: Optional experiment name 
        dataset_name: Optional dataset name
        confident_ai_streamed: Whether results were streamed to Confident AI
        
    Returns:
        Standardized evaluation response dictionary
    """
    meta = {
        "metrics_evaluated": metrics_count,
        "results_count": len(results),
        "confident_ai_streamed": confident_ai_streamed
    }
    
    if experiment_name:
        meta["experiment_name"] = experiment_name
    if dataset_name:
        meta["dataset_name"] = dataset_name
        
    return create_success_response(
        data={
            "results": results,
            "summary": {
                "total_metrics": metrics_count,
                "successful_evaluations": len([r for r in results if getattr(r, 'success', True)]),
                "failed_evaluations": len([r for r in results if not getattr(r, 'success', True)])
            }
        },
        message=f"Evaluation completed with {metrics_count} metrics",
        meta=meta
    )


def create_health_check_response(
    service_name: str = "RatioAI API",
    version: str = "1.0.0"
) -> Dict[str, Any]:
    """
    Create standardized health check response.
    
    Args:
        service_name: Name of the service
        version: Service version
        
    Returns:
        Health check response dictionary
    """
    return create_success_response(
        data={
            "service": service_name,
            "version": version, 
            "status": "healthy",
            "uptime": datetime.now(timezone.utc).isoformat()
        },
        message="Service is healthy"
    )


def create_validation_error_response(
    validation_errors: List[str]
) -> HTTPException:
    """
    Create standardized validation error response.
    
    Args:
        validation_errors: List of validation error messages
        
    Returns:
        HTTPException with validation error details
    """
    return create_error_response(
        error="Request validation failed",
        code=422,
        details={
            "validation_errors": validation_errors,
            "error_count": len(validation_errors)
        }
    )


def log_api_request(
    endpoint: str,
    method: str, 
    client_info: Optional[str] = None
) -> None:
    """
    Log API request for monitoring and debugging.
    
    Args:
        endpoint: API endpoint path
        method: HTTP method
        client_info: Optional client information
    """
    if client_info:
        logger.info("API Request: %s %s from %s", method, endpoint, client_info)
    else:
        logger.info("API Request: %s %s", method, endpoint)
