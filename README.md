# Spira Project Setup Tool

A config-driven Python script that provisions a complete Spira project structure via the Spira REST API v7. Define your programs, products, releases, custom fields, test folders, and test cases in a JSON file — then run one command.

## Features

- Creates Spira **products** and associates them with a program
- Creates **releases** (test periods) within products
- Creates **custom list fields** on test cases and test sets
- Creates **test case folders** and populates them with **test cases**
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
git clone https://github.com/dermotcanniffe/OetkerDemo.git
cd OetkerDemo
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
            {
              "name": "Field Name",
              "type": "list",
              "values": ["Value 1", "Value 2"]
            }
          ],
          "testSets": [
            {
              "name": "Country",
              "type": "list",
              "values": ["DE", "IT", "FR"]
            }
          ]
        },
        "testFolders": [
          {
            "name": "Folder Name",
            "testCases": [
              {
                "name": "Test Case Name",
                "description": "What this test case verifies."
              }
            ]
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
| `customFields.testCases` | No | List-type custom fields added to test cases |
| `customFields.testSets` | No | List-type custom fields added to test sets |
| `testFolders[].name` | No | Test case folder name |
| `testFolders[].testCases` | No | Test cases to create inside the folder |

## Project Structure

```
├── setup.py                        # Entry point
├── spira-structure.json            # Your client config (gitignored)
├── spira-structure.example.json    # Template to copy for new clients
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
        └── test_cases.py           # Test folders and test cases
```

## Adding a New Client

1. Copy `spira-structure.example.json` to a new file, e.g. `acme-structure.json`
2. Fill in the client's program, products, and test structure
3. Update `.env` with the client's Spira URL and your credentials
4. Run `python setup.py acme-structure.json`

You can maintain multiple structure files in the same repo — one per client, project phase, or environment — and pass the relevant file at runtime:

```bash
python setup.py acme-structure.json
python setup.py oetker-structure.json
python setup.py oetker-phase-b-structure.json
```

If no file is specified, `spira-structure.json` is used by default.

> **Working in a client-specific repo?** Remove the `spira-structure.json` line from `.gitignore` so your structure files are tracked. The comment in `.gitignore` explains when to do this.

## Authentication

Credentials are passed via HTTP headers on every request (`username` and `api-key`). They are never logged or printed. Keep your `.env` file out of source control — it is gitignored by default.
