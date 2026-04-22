# Ratio MCP Server
 
## Remote Prompt & Schema via Azure Data Lake Storage Gen2

The server can load the analyst prompt template and database schema text from
an Azure Data Lake Storage Gen2 container instead of local files.

Set the following environment variables to enable remote loading:

Required (remote enable):
- `ADLS_ACCOUNT_NAME`      Storage account name (without `.dfs.core.windows.net`)
- `ADLS_FILE_SYSTEM`       File system (container) name

Optional (paths, default to local-relative paths shown):
- `ADLS_PROMPT_PATH`       Path to prompt template in container (default: `prompts/airod_analyst_prompt.txt`)
- `ADLS_SCHEMA_PATH`       Path to schema file in container (default: `datasets/DatabaseSchema.txt`)

Credential options (choose one):
1. Account key:
	 - `ADLS_ACCOUNT_KEY`    Storage account key
2. Service Principal + Certificate (preferred, no key exposure):
	 - `ADLS_CLIENT_ID`      App registration (service principal) client ID
	 - `ADLS_TENANT_ID`      Azure AD tenant ID
	 - One certificate source:
		 - `ADLS_CERT_PEM_PATH` Local filesystem path to PEM file containing private key & cert
			 OR
		 - `ADLS_KEYVAULT_NAME` Name of Key Vault containing the PEM as a secret
			 - `ADLS_CERT_SECRET_NAME` Secret name with PEM contents
			 - `ADLS_CERT_SECRET_VERSION` (optional) Secret version

If no explicit credential variables are set the SDK falls back to
`DefaultAzureCredential` (managed identity, Azure CLI login, etc.).

### Uploading Files

Upload your local files to ADLS (examples use Azure CLI):

```powershell
az storage fs file upload `
	--account-name $Env:ADLS_ACCOUNT_NAME `
	--file-system $Env:ADLS_FILE_SYSTEM `
	--path prompts/airod_analyst_prompt.txt `
	--source .\src\prompts\airod_analyst_prompt.txt

az storage fs file upload `
	--account-name $Env:ADLS_ACCOUNT_NAME `
	--file-system $Env:ADLS_FILE_SYSTEM `
	--path datasets/DatabaseSchema.txt `
	--source .\src\datasets\DatabaseSchema.txt
```

## Certificate Auth Flow Summary

1. Create / register an App Registration (service principal) with access (RBAC role: Storage Blob Data Reader) to the storage account.
2. Generate a certificate (PEM) and add it to the App Registration as a credential.
3. Store the PEM either on disk (`ADLS_CERT_PEM_PATH`) or in Key Vault as a secret and set the Key Vault env vars.
4. Set `ADLS_CLIENT_ID` and `ADLS_TENANT_ID` so the server can build a `ClientCertificateCredential`.
5. Run the server; remote prompt/schema are fetched. Fallback to local files occurs automatically if remote read fails.

## Environment Variable Quick Reference

| Variable | Purpose |
|----------|---------|
| ADLS_ACCOUNT_NAME | Storage account name |
| ADLS_FILE_SYSTEM | Container (file system) name |
| ADLS_PROMPT_PATH | Path to prompt template in ADLS |
| ADLS_SCHEMA_PATH | Path to DB schema file in ADLS |
| ADLS_ACCOUNT_KEY | (Option 1) Account key credential |
| ADLS_CLIENT_ID | (Option 2) SPN client id for certificate auth |
| ADLS_TENANT_ID | Tenant id for SPN |
| ADLS_CERT_PEM_PATH | Local PEM file path for certificate auth |
| ADLS_KEYVAULT_NAME | Key Vault name if PEM stored as secret |
| ADLS_CERT_SECRET_NAME | Secret name containing PEM |
| ADLS_CERT_SECRET_VERSION | Optional secret version |

## Notes

Graceful fallback logic ensures that if remote configuration is partially
specified or fails, local files are used without raising an exception to the caller.

---

## Project Structure

```
src/
  server.py                 ← Entry point (HTTP/SSE and stdio transport)
  __init__.py
  core/                     ← Core runtime modules
    mcp_app.py              ← FastMCP instance, logging, telemetry, directory constants
    api_routes.py           ← Generic REST API dispatcher, call tracking endpoints
    call_tracker.py         ← Per-call audit tracking
    job_manager.py          ← In-memory async job manager
  registry/                 ← Config-driven MCP registration engines
    tools.py                ← Tool registration engine
    prompts.py              ← Prompt registration engine
    resources.py            ← Resource registration engine
  config/                   ← JSON configuration files (no code changes needed)
    tools_config.json       ← Tool definitions
    prompts_config.json     ← Prompt definitions
    resources_config.json   ← Resource definitions
  client/                   ← MCP client
    mcp_client.py           ← Client for stdio / streamable-http transports
  helper/                   ← Auth, data access, and utility modules
    auth.py                 ← JWT validation middleware
    lakehouse.py            ← Fabric / Synapse SQL connector
    kusto_auth.py           ← Kusto client with tiered auth
    adls.py                 ← ADLS Gen2 reader with tiered auth
    llm.py                  ← LLM helper
    normalize_entity_mapping.py
  plugins/                  ← Custom tool plugins (Python modules)
    normalize_entity.py
  queries/                  ← Externalized KQL query templates
    root_cause.kql
    impacted_resources.kql
  prompts/                  ← Prompt template text files (.txt)
  datasets/                 ← Static dataset files (JSON, text)
```

---

## Extensibility Guide — Adding Prompts, Tools, Resources & Plugins

The server uses a **config-driven architecture**. Adding new capabilities requires
only configuration + data files — no changes to Python code.

---

### Adding a New Prompt

Prompts are registered from `src/config/prompts_config.json`. Each prompt is a text
template file that is served to MCP clients.

**Steps:**

1. **Create the template file** in `src/prompts/`:

   ```
   src/prompts/my_new_prompt.txt
   ```

   Write your prompt text. Use the placeholder `{database_schema}` anywhere in
   the template if you want the database schema injected at runtime.

2. **Add an entry to `src/config/prompts_config.json`:**

   ```json
   {
     "name": "my_new_prompt",
     "description": "Short description shown to MCP clients.",
     "filename": "my_new_prompt.txt",
     "inject_schema": true
   }
   ```

   | Field           | Required | Description |
   |-----------------|----------|-------------|
   | `name`          | Yes      | Unique prompt name (used as the MCP prompt identifier). |
   | `description`   | Yes      | Human-readable description surfaced to clients. |
   | `filename`      | Yes      | File in `src/prompts/` (or ADLS remote path if remote enabled). |
   | `inject_schema` | No       | If `true`, replaces `{database_schema}` with the loaded DB schema. Default `false`. |

3. **Restart the server.** The new prompt will appear in `GET /api/prompts` and
   be available via the MCP protocol.

> **Remote prompts:** If `USE_REMOTE_FILES=true` and `ADLS_PROMPT_PATH` is set,
> the server first tries loading from ADLS and falls back to the local file.

---

### Adding a New Resource

Resources expose static datasets (JSON or text) to MCP clients. They are
registered from `src/config/resources_config.json`.

**Steps:**

1. **Drop your data file** into `src/datasets/`:

   ```
   src/datasets/MyLookupData.json
   ```

2. **Add an entry to `src/config/resources_config.json`:**

   ```json
   {
     "uri": "resource://my-lookup-data",
     "name": "my_lookup_data",
     "title": "My Lookup Data",
     "description": "Description for MCP clients.",
     "mime_type": "application/json",
     "filename": "MyLookupData.json",
     "type": "json"
   }
   ```

   | Field         | Required | Description |
   |---------------|----------|-------------|
   | `uri`         | Yes      | MCP resource URI (e.g. `resource://my-thing`). Must be unique. |
   | `name`        | Yes      | Unique resource name (Python identifier style). |
   | `title`       | Yes      | Human-readable title. |
   | `description` | Yes      | Description surfaced to MCP clients. |
   | `mime_type`   | Yes      | MIME type (`application/json` or `text/plain`). |
   | `filename`    | Yes      | File in `src/datasets/`. |
   | `type`        | Yes      | `"json"` or `"text"`. Controls the loader used. |

3. **Restart the server.** The resource is now listed in `GET /api/resources`
   and available via MCP `resources/read`.

> **Remote datasets:** If `USE_REMOTE_FILES=true` and `ADLS_RESOURCE_PATH` is
> set, the server tries ADLS first, then falls back to local.

---

### Adding a New Tool

Tools are registered from `src/config/tools_config.json`. Three tool types are
supported: **tsql**, **kusto**, and **plugin**.

#### Tool Type: `tsql`

Executes a parameterized T-SQL query against a Fabric lakehouse or Synapse
SQL endpoint.

**Add an entry to `src/config/tools_config.json`:**

```json
{
  "name": "my_tsql_tool",
  "type": "tsql",
  "description": "Description for MCP clients.\n\nParameters:\n    query (str): ...\n    max_rows (int): ...\n\nReturns:\n    JSON {\"rows\": [...], \"count\": N}",
  "parameters": {
    "query": {
      "type": "string",
      "required": true,
      "description": "The SELECT statement to execute."
    },
    "max_rows": {
      "type": "integer",
      "required": false,
      "default": 100,
      "description": "Maximum rows to return."
    }
  },
  "blocked_prefixes": ["drop", "delete", "update", "insert", "alter", "truncate"]
}
```

**Optional — target a different SQL endpoint** (e.g. Synapse instead of Fabric):

```json
{
  "endpoint_env": "SYNAPSE_SQL_ENDPOINT",
  "database_env": "SYNAPSE_SQL_DATABASE"
}
```

When `endpoint_env` / `database_env` are set, the handler reads those env vars
and passes them to the SQL connector, overriding the default Fabric endpoint.

| Field              | Required | Description |
|--------------------|----------|-------------|
| `name`             | Yes      | Unique tool name. |
| `type`             | Yes      | `"tsql"` |
| `description`      | Yes      | Description (surfaced to MCP clients). Include parameter/return docs. |
| `parameters`       | Yes      | Parameter definitions (see Parameter Schema below). |
| `blocked_prefixes` | No       | List of SQL verbs to block (e.g. `["drop","delete"]`). |
| `endpoint_env`     | No       | Env var name for SQL endpoint override. |
| `database_env`     | No       | Env var name for database override. |

#### Tool Type: `kusto`

Executes a parameterized KQL query against an Azure Data Explorer cluster.

**Steps:**

1. **Create a KQL query file** in `src/queries/`:

   ```
   src/queries/my_query.kql
   ```

   Use Kusto `declare query_parameters (...)` syntax for parameterized queries:

   ```kql
   declare query_parameters (MyParam:string);
   MyTable
   | where Column == MyParam
   | take 100
   ```

2. **Add an entry to `src/config/tools_config.json`:**

   ```json
   {
     "name": "my_kusto_tool",
     "type": "kusto",
     "description": "Description for MCP clients.",
     "cluster_env": "MY_KUSTO_CLUSTER",
     "database_env": "MY_KUSTO_DATABASE",
     "query_file": "my_query.kql",
     "parameters": {
       "my_param": {
         "type": "string",
         "required": true,
         "description": "A filter value."
       }
     },
     "kusto_params": {
       "MyParam": {
         "source": "my_param"
       }
     }
   }
   ```

   | Field          | Required | Description |
   |----------------|----------|-------------|
   | `name`         | Yes      | Unique tool name. |
   | `type`         | Yes      | `"kusto"` |
   | `cluster_env`  | Yes      | Env var name holding the Kusto cluster URI. |
   | `database_env` | Yes      | Env var name holding the database name. |
   | `query_file`   | Yes      | Filename in `src/queries/`. |
   | `parameters`   | Yes      | Parameter definitions (see Parameter Schema below). |
   | `kusto_params` | Yes      | Mapping of KQL `declare query_parameters` names → tool parameter sources. |
   | `validation`   | No       | Validation rules (see Time Range Validation below). |

   **`kusto_params` mapping:**

   ```json
   "kusto_params": {
     "<KQL_PARAM_NAME>": {
       "source": "<tool_parameter_name>",
       "cast": "int"
     }
   }
   ```

   - `source`: Which tool parameter to read the value from.
   - `cast` (optional): `"int"` to cast the value to integer before sending to Kusto.

   **Time range validation** (optional):

   ```json
   "validation": {
     "time_range": {
       "start_param": "start_time",
       "end_param": "end_time",
       "max_days": 30,
       "max_age_days": 30
     }
   }
   ```

   Enforces ISO 8601 format, `end >= start`, max window size, and max age from now.

#### Tool Type: `plugin`

Delegates to a custom Python module. Use this for tools that need arbitrary
logic beyond simple query execution.

**Steps:**

1. **Create a plugin module** in `src/plugins/`:

   ```
   src/plugins/my_plugin.py
   ```

   The module must expose an **async entry function** matching the tool's
   parameters:

   ```python
   """Plugin: my_custom_tool"""
   import json

   async def run(input_text: str, max_results: int = 10) -> str:
       """Entry point called by the tool registry."""
       # Your custom logic here
       result = {"output": f"Processed: {input_text}", "count": max_results}
       return json.dumps(result)
   ```

   **Rules:**
   - The entry function must be `async` and return a JSON string.
   - Function signature parameters become the tool's input schema automatically.
   - You can import from `core.mcp_app`, `registry.resources`, `helper.*`, etc.

2. **Add an entry to `src/config/tools_config.json`:**

   ```json
   {
     "name": "my_custom_tool",
     "type": "plugin",
     "description": "Description for MCP clients.",
     "module": "plugins.my_plugin",
     "entry_function": "run",
     "parameters": {
       "input_text": {
         "type": "string",
         "required": true,
         "description": "Text to process."
       },
       "max_results": {
         "type": "integer",
         "required": false,
         "default": 10,
         "description": "Max results to return."
       }
     }
   }
   ```

   | Field            | Required | Description |
   |------------------|----------|-------------|
   | `name`           | Yes      | Unique tool name. |
   | `type`           | Yes      | `"plugin"` |
   | `module`         | Yes      | Python module path (dot-separated, relative to `src/`). |
   | `entry_function` | Yes      | Name of the async function to call in the module. |
   | `description`    | Yes      | Description surfaced to MCP clients. |
   | `parameters`     | Yes      | Parameter definitions (see Parameter Schema below). |

---

### Parameter Schema Reference

All tool types use the same parameter schema format:

```json
"parameters": {
  "<param_name>": {
    "type": "<type>",
    "required": true,
    "default": "<value>",
    "description": "Human-readable description."
  }
}
```

| Field         | Required | Description |
|---------------|----------|-------------|
| `type`        | Yes      | One of: `string`, `integer`, `number`, `boolean`, `object`, `array`. |
| `required`    | No       | `true` if the parameter is mandatory. Default `false`. |
| `default`     | No       | Default value when not supplied by the caller. |
| `description` | Yes      | Description shown in the tool schema. |

---

### Quick Reference — What to Create

| What to add     | Config file                       | Data / code file                | Code changes? |
|-----------------|-----------------------------------|---------------------------------|---------------|
| New prompt      | `src/config/prompts_config.json`  | `src/prompts/<name>.txt`        | **None**       |
| New resource    | `src/config/resources_config.json`| `src/datasets/<file>`           | **None**       |
| New tsql tool   | `src/config/tools_config.json`    | —                               | **None**       |
| New kusto tool  | `src/config/tools_config.json`    | `src/queries/<name>.kql`        | **None**       |
| New plugin tool | `src/config/tools_config.json`    | `src/plugins/<module>.py`       | **None** (only the new plugin file) |

After adding, restart the server. All new prompts, resources, and tools are
automatically registered and appear in `GET /api/prompts`, `GET /api/resources`,
`GET /api/tools`, and through the MCP protocol.
## Get started with the Weather MCP Server template

> **Prerequisites**
>
> To run the MCP Server in your local dev machine, you will need:
>
> - [Python](https://www.python.org/)
> - (*Optional - if you prefer uv*) [uv](https://github.com/astral-sh/uv)
> - [Python Debugger Extension](https://marketplace.visualstudio.com/items?itemName=ms-python.debugpy)

## Prepare environment

There are two approaches to set up the environment for this project. You can choose either one based on your preference.

> Note: Reload VSCode or terminal to ensure the virtual environment python is used after creating the virtual environment.

| Approach | Steps |
| -------- | ----- |
| Using `uv` | 1. Create virtual environment: `uv venv` <br>2. Run VSCode Command "***Python: Select Interpreter***" and select the python from created virtual environment <br>3. Install dependencies (include dev dependencies): `uv pip install -r pyproject.toml --extra dev` |
| Using `pip` | 1. Create virtual environment: `python -m venv .venv` <br>2. Run VSCode Command "***Python: Select Interpreter***" and select the python from created virtual environment<br>3. Install dependencies (include dev dependencies): `pip install -e .[dev]` | 

After setting up the environment, you can run the server in your local dev machine via Agent Builder as the MCP Client to get started:
1. Open VS Code Debug panel. Select `Debug in Agent Builder` or press `F5` to start debugging the MCP server.
2. Use AI Toolkit Agent Builder to test the server with [this prompt](vscode://ms-windows-ai-studio.windows-ai-studio/open_prompt_builder?model_id=github/gpt-4o-mini&system_prompt=You%20are%20a%20weather%20forecast%20professional%20that%20can%20tell%20weather%20information%20based%20on%20given%20location&user_prompt=What%20is%20the%20weather%20in%20Shanghai?&track_from=vsc_md&mcp=ratio_mcp). Server will be auto-connected to the Agent Builder.
3. Click `Run` to test the server with the prompt.

**Congratulations**! You have successfully run the Weather MCP Server in your local dev machine via Agent Builder as the MCP Client.
![DebugMCP](https://raw.githubusercontent.com/microsoft/windows-ai-studio-templates/refs/heads/dev/mcpServers/mcp_debug.gif)

## What's included in the template

| Folder / File  | Contents                                           |
| -------------- | -------------------------------------------------- |
| `.vscode`      | VSCode files for debugging                         |
| `.aitk`        | Configurations for AI Toolkit                      |
| `src/server.py`| Entry point — HTTP/SSE and stdio transport         |
| `src/core/`    | MCP app instance, API routes, call tracking, jobs  |
| `src/registry/`| Config-driven registration for tools/prompts/resources |
| `src/config/`  | JSON config files (tools, prompts, resources)      |
| `src/client/`  | MCP client for stdio / streamable-http             |
| `src/helper/`  | Auth, lakehouse, Kusto, ADLS, LLM utilities        |
| `src/plugins/` | Custom tool plugin modules                         |
| `src/queries/` | Externalized KQL query templates                   |
| `src/prompts/` | Prompt template text files                         |
| `src/datasets/`| Static dataset files (JSON, text)                  |

## How to debug the Weather MCP Server

> Notes:
> - [MCP Inspector](https://github.com/modelcontextprotocol/inspector) is a visual developer tool for testing and debugging MCP servers.
> - All debugging modes support breakpoints, so you can add breakpoints to the tool implementation code.

| Debug Mode | Description | Steps to debug |
| ---------- | ----------- | --------------- |
| Agent Builder | Debug the MCP server in the Agent Builder via AI Toolkit. | 1. Open VS Code Debug panel. Select `Debug in Agent Builder` and press `F5` to start debugging the MCP server.<br>2. Use AI Toolkit Agent Builder to test the server with [this prompt](vscode://ms-windows-ai-studio.windows-ai-studio/open_prompt_builder?model_id=github/gpt-4o-mini&system_prompt=You%20are%20a%20weather%20forecast%20professional%20that%20can%20tell%20weather%20information%20based%20on%20given%20location&user_prompt=What%20is%20the%20weather%20in%20Shanghai?&track_from=vsc_md&mcp=ratio_mcp). Server will be auto-connected to the Agent Builder.<br>3. Click `Run` to test the server with the prompt. |
| MCP Inspector | Debug the MCP server using the MCP Inspector. | 1. Install [Node.js](https://nodejs.org/)<br> 2. Set up Inspector: `cd inspector` && `npm install` <br> 3. Open VS Code Debug panel. Select `Debug SSE in Inspector (Edge)` or `Debug SSE in Inspector (Chrome)`. Press F5 to start debugging.<br> 4. When MCP Inspector launches in the browser, click the `Connect` button to connect this MCP server.<br> 5. Then you can `List Tools`, select a tool, input parameters, and `Run Tool` to debug your server code.<br> |

## Prompt Tool Usage

`build_prompt` can be invoked with the following parameters:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `schema` | string (JSON) | No* | JSON Schema string. Required unless `return_placeholder` is `True`. |
| `goal` | string | No | High-level purpose for the generated data. Defaults to a generic goal. |
| `return_placeholder` | boolean | No | When `True`, returns a template containing `{{schema}}` so you can inject a schema later. |

Example (inline schema):
```
Tool: build_prompt
Input:
	schema: {"type":"object","properties":{"id":{"type":"string"},"tags":{"type":"array","items":{"type":"string"}}},"required":["id"]}
	goal: Produce an example record for tagging system
	return_placeholder: false
```

Example (placeholder template):
```
Tool: build_prompt
Input:
	return_placeholder: true
```

Returned prompt will include either the pretty-printed schema or the `{{schema}}` placeholder token ready for substitution.

## T-SQL Query Tool

A new tool `run_tsql_query_tool` has been added for executing read-only T-SQL queries against the configured Fabric lakehouse.

Parameters:
- `query` (string, required): T-SQL SELECT statement.
- `max_rows` (integer, optional): Client-side limit of returned rows.

Safety: Statements beginning with DROP/DELETE/UPDATE/INSERT/ALTER/TRUNCATE are blocked.

Example:
```
Tool: run_tsql_query_tool
Input:
    query: SELECT TOP 10 * FROM dbo.SomeTable
    max_rows: 10
```
Returns JSON:
```
{"rows": [{"Col1": "Value", ...}, ...], "count": 10}
```

Environment variables required for connection (see `src/lakehouse.py`):
- `FABRIC_SQL_ENDPOINT`
- `FABRIC_SQL_DATABASE`
- `AUTH_TENANT_ID`
- `FABRIC_APP_ID`
- `AUTH_CLIENT_ID`
- `CERT_NAME`
- `KEY_VAULT_NAME`

If connection fails, the tool returns `{"rows": [], "count": 0}` or an `{"error": "..."}` message.

## Default Ports and customizations

| Debug Mode | Ports | Definitions | Customizations | Note |
| ---------- | ----- | ------------ | -------------- |-------------- |
| Agent Builder | 3001 | [tasks.json](.vscode/tasks.json) | Edit [launch.json](.vscode/launch.json), [tasks.json](.vscode/tasks.json), [\_\_init\_\_.py](src/__init__.py), [mcp.json](.aitk/mcp.json) to change above ports. | N/A |
| MCP Inspector | 3001 (Server); 5173 and 3000 (Inspector) | [tasks.json](.vscode/tasks.json) | Edit [launch.json](.vscode/launch.json), [tasks.json](.vscode/tasks.json), [\_\_init\_\_.py](src/__init__.py), [mcp.json](.aitk/mcp.json) to change above ports.| N/A |

## Feedback

If you have any feedback or suggestions for this template, please open an issue on the [AI Toolkit GitHub repository](https://github.com/microsoft/vscode-ai-toolkit/issues)

## Programmatic Client Usage

## REST API Endpoints

In addition to MCP protocol tooling over `/mcp`, the server exposes simple JSON REST endpoints for direct HTTP integration.

Machine-readable spec: `GET /api/openapi.json`

Human-readable summary (wrapped in JSON with a `markdown` field): `GET /api/docs`

### 1. Normalize Entity Mapping

`POST /api/normalize_entity_mapping`

Request body:
```json
{
	"entity_mapping": {"ServiceName": "?", "Offering": "?", "Region": "?"},
	"user_ask": "Original user question or context"
}
```

Response (success):
```json
{
	"normalized": {"service": "...", "offering": "...", "region": "..."},
	"variants": {"service": ["..."], "offering": ["..."], "region": ["..."]},
	"source": "synonyms"
}
```
Response (error):
```json
{"error": "message"}
```

PowerShell example:
```powershell
$body = @{ entity_mapping = @{ ServiceName = 'Compute'; Offering = 'VM'; Region = 'East US' }; user_ask = 'Show recent outages' } | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method POST -Uri http://localhost:8000/api/normalize_entity_mapping -Body $body -ContentType 'application/json'
```

### 2. Run T-SQL Query

`POST /api/run_tsql_query`

Request body:
```json
{
	"query": "SELECT TOP 10 IncidentId, Offering FROM OfferingOutageAiro ORDER BY OutageCreateDate DESC",
	"max_rows": 10
}
```
Notes:
- `query` must be a non-empty SELECT-style statement.
- Leading destructive verbs (DROP/DELETE/UPDATE/INSERT/ALTER/TRUNCATE) are blocked.
- `max_rows` is optional; if omitted the default (100) applies.

Response (success):
```json
{
	"rows": [ {"IncidentId": 123, "Offering": "Compute"}, ... ],
	"count": 10
}
```
Response (error):
```json
{"error": "message"}
```

PowerShell example:
```powershell
$body = @{ query = 'SELECT TOP 5 IncidentId, Offering FROM OfferingOutageAiro'; max_rows = 5 } | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method POST -Uri http://localhost:8000/api/run_tsql_query -Body $body -ContentType 'application/json'
```

### Authentication

If `AUTH_ENABLED=true` the endpoints require a bearer token. Add the header:
```
Authorization: Bearer <access_token>
```
See the Authentication Middleware section below for obtaining tokens.

### Error Handling

Both endpoints return standard JSON error payloads with HTTP 4xx for validation issues and 5xx for unexpected server errors:
```json
{"error": "Invalid body. Expect non-empty query (string)."}
```
Always check for an `error` key before processing `rows`.

### Health Check

`GET /health` returns:
```json
{"status": "ok"}
```
Use this for liveness probes (consider adding to `AUTH_BYPASS_PATHS`).


You can now interact with the MCP server directly from Python code without invoking the CLI arguments using the `McpLocalClient` or convenience helpers in `mcp_client`.

### Async usage
```python
from src.mcp_client import McpLocalClient

async def main():
	async with McpLocalClient() as client:
		tools = await client.list_tools()
		print("Tools:", tools)
		prompts = await client.list_prompts()
		print("Prompts:", prompts)
		output_texts = await client.call_tool("build_airod_analyst_prompt")
		print("Tool output:")
		print("\n".join(output_texts))
		prompt_def = await client.get_prompt("airod_analyst")
		print("Prompt definition:", prompt_def)

# asyncio.run(main())
```

### Synchronous helpers
```python
from src.mcp_client import run_tool, get_prompt_sync

texts = run_tool("build_airod_analyst_prompt")
print("Tool output:", "\n".join(texts))

prompt_def = get_prompt_sync("airod_analyst")
print("Prompt definition:", prompt_def)
```

These helpers spawn a local stdio server using environment variables `MCP_PYTHON` and `MCP_SERVER_ENTRY` when set, falling back to the current interpreter and `__init__` entry module.

### Streamable HTTP Endpoint Note

When using the streamable-http transport directly, the active API root is exposed under the `/mcp` path. The Python client now auto-appends `/mcp` if you pass a base URL without it:

```
python -m src.prompt_client --url http://localhost:8000 --list  # becomes http://localhost:8000/mcp
```

If you explicitly include `/mcp`, it is used as-is:

```
python -m src.prompt_client --url http://localhost:8000/mcp --list
```

If you encounter `404 Not Found` or `Session terminated`, verify the server is running on the expected port and that the `/mcp` suffix is present (or let the client add it automatically). Future improvement: retry once with `/mcp` on initial 404.
\n## Authentication Middleware (Azure AD / Managed Identity)\n\nYou can enable bearer token authentication so only authorized Azure AD principals can call the MCP HTTP endpoints.\n\nEnable by setting `AUTH_ENABLED=true` and supplying configuration via environment variables:\n\n| Variable | Purpose |\n|----------|---------|\n| AUTH_ENABLED | Set to `true` to activate middleware |\n| AUTH_TENANT_ID | (Optional) Restrict tokens to this tenant id (`tid`) |\n| AUTH_AUDIENCE | Expected `aud` claim (App Registration client id or Application ID URI) |\n| AUTH_ALLOWED_CLIENT_IDS | (Optional) Comma-separated allow list for `appid` or `azp` claim |\n| AUTH_BYPASS_PATHS | (Optional) Comma-separated paths to skip auth (e.g. `/health,/metrics`) |\n\nWhen enabled, requests must send an `Authorization: Bearer <token>` header. A 401 JSON response is returned on failure:\n```json\n{"error": "unauthorized", "reason": "audience mismatch"}\n```\n\n### Obtaining a Token\n\nManaged Identity (inside Azure resource):\n```powershell\n# Azure Instance Metadata Service (system-assigned MI)\n$resource = "api://<your-app-client-id-or-app-id-uri>"  # matches AUTH_AUDIENCE\nInvoke-RestMethod -Headers @{Metadata="true"} -Method GET -Uri "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2019-11-01&resource=$resource" | Select-Object -ExpandProperty access_token\n```\n\nService Principal (client credential flow) using certificate (PowerShell Az module):\n```powershell\n$tenant = $Env:AUTH_TENANT_ID\n$clientId = "<app-registration-client-id>"\n# Login with certificate (ensure cert installed in CurrentUser\My)\nConnect-AzAccount -ServicePrincipal -Tenant $tenant -ApplicationId $clientId -CertificateThumbprint <thumbprint>\n$token = (Get-AzAccessToken -TenantId $tenant -ResourceUrl "api://$clientId").Token\n# Use: Authorization: Bearer $token\n```\n\nLocal dev (Azure CLI logged in):\n```powershell\n$aud = "api://<your-app-client-id>"\n$token = az account get-access-token --resource $aud --query accessToken -o tsv\n```\n\n### Runtime Behavior\nMiddleware validates signature via Azure AD JWKS for the tenant, enforces `aud`, optional tenant `tid`, and optional client id allow list (`appid` or `azp`). Valid claims are attached to the ASGI scope as `auth_claims` for downstream logic.\n\n### Health Endpoint Recommendation\nIf you expose a simple health check route add it to `AUTH_BYPASS_PATHS` so orchestration probes do not require a token.\n\n### Extending\n`src/auth.py` contains the middleware. You can extend it to add role-based authorization, cache JWKS longer, enforce specific scopes (`scp` claim), or integrate with API Management.\n*** End Patch