# Spira Project Setup Tool

A config-driven Python script that provisions a complete Spira project structure via the Spira REST API v7. Define your programs, products, releases, custom fields, test folders, and test cases in a JSON file — then run one command.

**[▶ View presentation](https://dermotcanniffe.github.io/SpiraProvisioner/)**

## How It Works

```mermaid
flowchart TD
    A([User runs setup.py]) --> B[Load .env credentials]
    B --> C[Load structure JSON file]
    C --> D{Connect to\nSpira API}
    D -->|Connection failed| E([Exit with error])
    D -->|OK| F[Verify program exists\nin Spira admin UI]

    F --> G[For each product]

    G --> H[Create product / skip if exists]
    H --> I[Resolve project template ID]

    I --> J[For each release]
    J --> K[Create release / skip if exists]

    I --> L[For each custom field]
    L --> M[Create custom list with values]
    M --> N[Create custom property on artifact]

    I --> O[For each test folder]
    O --> P[Create folder / skip if exists]
    P --> Q[For each test case]
    Q --> R[Create test case / skip if exists]

    I --> REQ[For each requirement]
    REQ --> REQ2[Create requirement hierarchy\ndepth-first]

    I --> RSK[For each risk]
    RSK --> RSK2[Create risk / skip if exists]

    I --> TSK[For each task]
    TSK --> TSK2[Create task / skip if exists]

    R --> ASSOC
    REQ2 --> ASSOC
    RSK2 --> ASSOC
    TSK2 --> ASSOC[For each association]
    ASSOC --> ASSOC2[Route to correct endpoint\nand create link]

    K --> S
    N --> S
    ASSOC2 --> S([Print summary & exit])

    style E fill:#f66,color:#fff
    style S fill:#2d9,color:#fff
```

## Features

- Creates Spira **products** and associates them with a program
- Creates **releases** (test periods) within products
- Creates **custom list fields** on test cases and test sets (supports list, multilist, text, integer, decimal, boolean, date, datetime, user, and release types)
- Creates **test case folders** and populates them with **test cases**
- Creates hierarchical **requirements** (with unlimited nesting depth)
- Creates **risks** with optional probability and impact ratings
- Creates **tasks** with optional task type assignment
- Creates **associations** between artifacts with smart endpoint routing:
  - Requirement → Test Case: uses the coverage endpoint (appears in Test Cases tab)
  - Requirement → Task: links via `RequirementId` (appears in Tasks tab, enables progress tracking)
  - Risk → Task: links via `RiskId` (appears in Risk's Tasks tab)
  - Release → Test Case: maps test cases to releases for execution tracking
  - All other combinations: creates a generic "Related To" association
- Fully **idempotent** — safe to re-run; existing resources are skipped
- Config-driven — no code changes needed for new clients or projects

## Prerequisites

- Python 3.11+
- A Spira instance (SpiraTest, SpiraTeam, or SpiraPlan) with API access
- A Spira user with sufficient permissions (Product Owner or System Admin recommended)

> **Note:** Programs (portfolios) cannot be created via the Spira REST API. Create the program manually in the Spira admin UI before running this script.

## Setup

**1. Clone the repo**

```bash
git clone https://github.com/dermotcanniffe/SpiraProvisioner.git
cd SpiraProvisioner
```

**2. Install dependencies**

```bash
pip install -r requirements.txt
```

**3. Configure credentials**

Copy the example env file and fill in your Spira details:

```bash
cp .env.example .env
```

Edit `.env`:

```
SPIRA_BASE_URL=https://your-instance.spiraservice.net/
SPIRA_USERNAME=your-username
SPIRA_API_KEY={your-api-key}
```

Your API key is your Spira RSS token. Find it under your user profile in Spira — include the curly braces.

**4. Define your project structure**

Copy the example structure file and edit it for your client:

```bash
cp spira-structure.example.json spira-structure.json
```

Edit `spira-structure.json` with your program name, products, releases, custom fields, and test cases. See [Structure File Reference](#structure-file-reference) below.

**5. Run the script**

```bash
# Use the default spira-structure.json
python setup.py

# Or specify a named structure file
python setup.py my-client-structure.json
```

The script will print a summary of everything created when it completes.

## Structure File Reference

```json
{
  "program": {
    "name": "Your Portfolio Name",
    "products": [
      {
        "name": "Your Product Name",
        "releases": [
          { "name": "Release 1" }
        ],
        "customFields": {
          "testCases": [
            { "name": "Field Name", "type": "list", "values": ["Value 1", "Value 2"] }
          ],
          "testSets": [
            { "name": "Country", "type": "list", "values": ["DE", "IT", "FR"] }
          ]
        },
        "testFolders": [
          {
            "name": "Folder Name",
            "testCases": [
              { "name": "Test Case Name", "description": "What this test case verifies." }
            ]
          }
        ],
        "requirements": [
          {
            "name": "Parent Requirement",
            "description": "Top-level requirement.",
            "children": [
              { "name": "Child Requirement", "description": "Nested under parent." }
            ]
          }
        ],
        "risks": [
          { "name": "Risk Name", "description": "What could go wrong.", "probability": 3, "impact": 4 }
        ],
        "tasks": [
          { "name": "Task Name", "description": "What needs doing.", "taskType": "Development" }
        ],
        "associations": [
          {
            "sourceType": "requirement",
            "source": "Parent Requirement",
            "destType": "testCase",
            "dest": "Test Case Name",
            "comment": "Covered by this test"
          },
          {
            "sourceType": "requirement",
            "source": "Parent Requirement",
            "destType": "task",
            "dest": "Task Name"
          },
          {
            "sourceType": "risk",
            "source": "Risk Name",
            "destType": "task",
            "dest": "Task Name",
            "comment": "Mitigated by this task"
          }
        ]
      }
    ]
  }
}
```

| Field | Required | Description |
|---|---|---|
| `program.name` | Yes | Must match an existing program in Spira (created via admin UI) |
| `products[].name` | Yes | Display name for the product/project |
| `releases[].name` | No | Display name for the release (created as Sprint type) |
| `customFields.testCases` | No | Custom fields added to test cases |
| `customFields.testSets` | No | Custom fields added to test sets |
| `testFolders[].name` | No | Test case folder name |
| `testFolders[].testCases` | No | Test cases to create inside the folder |
| `requirements[].name` | No | Requirement name (supports nesting via `children`) |
| `requirements[].children` | No | Child requirements nested under the parent |
| `risks[].name` | No | Risk name |
| `risks[].probability` | No | Likelihood rating (1–5) |
| `risks[].impact` | No | Impact severity rating (1–5) |
| `tasks[].name` | No | Task name |
| `tasks[].taskType` | No | Task type name (resolved at runtime; falls back to default) |
| `associations[]` | No | Links between artifacts (see below) |

**Associations fields:**

| Field | Required | Description |
|---|---|---|
| `sourceType` | Yes | Source artifact type: `requirement`, `testCase`, `incident`, `release`, `task`, `risk` |
| `source` | Yes | Display name of the source artifact (must exist in the same product) |
| `destType` | Yes | Destination artifact type (same options as `sourceType`) |
| `dest` | Yes | Display name of the destination artifact |
| `comment` | No | Free-text description of the association |

**How associations are routed:**

The provisioner automatically uses the correct Spira API endpoint based on the source/dest combination to ensure traceability works:

| Source → Dest | Spira Behaviour |
|---|---|
| requirement → testCase | Creates test coverage (shows in requirement's Test Cases tab) |
| requirement → task | Links task to requirement (shows in requirement's Tasks tab) |
| risk → task | Links task to risk (shows in risk's Tasks tab) |
| release → testCase | Maps test case to release (shows in release's Test Cases tab) |
| Any other combination | Creates a generic "Related To" association |

**Supported custom field types:**

| `type` | Description | Requires `values`? |
|---|---|---|
| `list` | Single-select dropdown | Yes |
| `multilist` | Multi-select dropdown | Yes |
| `text` | Free-text string | No |
| `integer` | Whole number | No |
| `decimal` | Floating-point number | No |
| `boolean` | Yes/No toggle | No |
| `date` | Date picker | No |
| `datetime` | Date and time picker | No |
| `user` | Spira user picker | No |
| `release` | Spira release picker | No |

## Project Structure

```
├── setup.py                        # Entry point
├── spira-structure.json            # Your client config (gitignored)
├── spira-structure.example.json    # Template to copy for new clients
├── spira-structure.schema.json     # JSON Schema for editor support & LLM generation
├── .env                            # Your credentials (gitignored)
├── .env.example                    # Credential template
├── requirements.txt
└── spira_setup/
    ├── client.py                   # HTTP client — auth, retries, error handling
    ├── runner.py                   # Orchestrates setup from the structure file
    └── services/
        ├── projects.py             # Create/find products and programs
        ├── releases.py             # Create releases
        ├── templates.py            # Custom lists and custom properties
        ├── test_cases.py           # Test folders and test cases
        ├── requirements.py         # Hierarchical requirements
        ├── risks.py                # Risks with probability/impact
        ├── tasks.py                # Tasks with type assignment
        └── associations.py         # Cross-artifact links and traceability
```

## Adding a New Client

1. Copy `spira-structure.example.json` to a new file, e.g. `acme-structure.json`
2. Fill in the client's program, products, and test structure
3. Update `.env` with the client's Spira URL and your credentials
4. Run `python setup.py acme-structure.json`

You can maintain multiple structure files in the same repo — one per client, project phase, or environment — and pass the relevant file at runtime:

```bash
python setup.py acme-structure.json
python setup.py client-b-structure.json
python setup.py client-b-phase-2-structure.json
```

If no file is specified, `spira-structure.json` is used by default.

> **Working in a client-specific repo?** Remove the `spira-structure.json` line from `.gitignore` so your structure files are tracked. The comment in `.gitignore` explains when to do this.

## Generating Structure Files with an LLM

The `spira-structure.schema.json` file in this repo is a [JSON Schema](https://json-schema.org/) that formally describes every field the setup script accepts. You can use it to generate valid structure files from a plain-English brief using any LLM (ChatGPT, Claude, Kiro, Copilot, etc.).

**How to use it:**

Include the schema in your prompt, then describe what you need:

> *"Using the attached JSON Schema, generate a Spira structure file for a logistics client. They need two products — one for their WMS system and one for their TMS system. Each product needs releases for Q3 and Q4 2025. Test cases should cover order creation, shipment tracking, and returns processing. Add a Country custom field (DE, IT, FR) to test sets."*

The LLM will produce a ready-to-run structure file that conforms to the schema.

**Editor support:**

Any structure file that includes the `$schema` reference (as in `spira-structure.example.json`) will get live autocomplete and validation in VS Code and other JSON-aware editors — no plugin required.

```json
{
  "$schema": "./spira-structure.schema.json",
  "program": { ... }
}
```

**What the schema enforces:**

- Required fields (`name` is required everywhere)
- Field types and length limits
- Valid values for `type` (currently only `"list"`)
- No unexpected extra fields (`additionalProperties: false`)
- Descriptive `description` fields on every property explaining intent to both humans and LLMs

## Extending the Tool

The codebase is designed to make adding new Spira artifact types straightforward. Here's how to approach the most common extension scenarios.

**Adding a new artifact type (e.g. test sets, incidents)**

1. Create a new file in `spira_setup/services/`, e.g. `test_sets.py`
2. Follow the same pattern as the existing service files:
   - A `get_all_*` function that calls `client.get(...)`
   - A `get_*_by_name` function for idempotency checks
   - A `create_*` function that checks for existence first, then POSTs
3. Add the new artifact to the structure JSON schema (and update `spira-structure.example.json`)
4. Call your new service functions from `runner.py` in the appropriate place in the per-product loop

**Adding a new association routing rule**

If Spira has a dedicated endpoint for a specific artifact combination (like requirement → test case has the coverage endpoint), add it to `associations.py`:

1. Create a helper function (e.g. `_create_my_link(...)`) following the pattern of `_create_requirement_test_coverage`
2. Add a routing check in `create_associations` before the generic fallback
3. The generic associations endpoint remains the catch-all for combinations without a dedicated API

**Changing what the script reads from the JSON**

All structure parsing happens in `runner.py`. The JSON shape is intentionally simple — if you need to add new fields to a product or test case definition, add them to the JSON and read them in `runner.py`. No other files need to change.

**Calling the Spira API directly**

All HTTP calls go through `spira_setup/client.py`. The `SpiraClient` class exposes `get`, `post`, `put`, and `delete` methods. Use these rather than calling `requests` directly — you get auth, retries, and error handling for free.

```python
from spira_setup.client import SpiraClient

client = SpiraClient(base_url, username, api_key)

# GET
projects = client.get("projects")

# POST
new_item = client.post("projects/{id}/test-cases", {"Name": "My Test", ...})

# PUT
client.put("projects/{id}/releases", updated_body)
```

The full list of available endpoints is documented at `{your-spira-url}/Services/v7_0/RestService.aspx`.

## Authentication

Credentials are passed via HTTP headers on every request (`username` and `api-key`). They are never logged or printed. Keep your `.env` file out of source control — it is gitignored by default.

**Managing multiple environments:**

You can keep instance-specific env files using the `.<identifier>.env` pattern:

```
.production.env
.staging.env
.dermot.env
```

These are all gitignored automatically. To switch environments, copy the one you need:

```bash
cp .production.env .env
```

The `.env.example` file is always tracked in source control as a template.
