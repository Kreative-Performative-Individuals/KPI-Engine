# KPI-Engine

[![CI](https://img.shields.io/github/actions/workflow/status/Kreative-Performative-Individuals/KPI-Engine/ci.yml)](https://github.com/Kreative-Performative-Individuals/KPI-Engine/actions)
[![License](https://img.shields.io/github/license/Kreative-Performative-Individuals/KPI-Engine)](https://github.com/Kreative-Performative-Individuals/KPI-Engine/blob/dev/LICENSE)


The KPI Calculation Engine is a Python library that provides the core logic when it comes to compute requested KPIs from a given storage system.

--- 

## 📁 Contents

The repository contains the following directories
```
📂 Project Root
├── 📂 src
│   ├── 📂 app
│   │   ├── 📂 api
│   │   │   └── 📂 endpoints
│   │   ├── 📂 kpi_engine
│   │   │   └── 📂 dynamic
│   │   ├── 📂 models
│   │   │   ├── 📂 requests
│   │   │   └── 📂 responses
│   │   ├── 📂 services
│   │   ├── 📂 utils
│   │   └── 🌐 main.py
│   ├── 📂 tests
│   │   └── 🧪 test_dynamic_calc.py
├── 🔄 .github
├── 📜 LICENSE
├── 📖 README.md
├── 🐳 Dockerfile
├── 🛠 pyproject.toml
└── 🛠 poetry.lock
```
In order, the directories and main files are the following
- **`src`**
   A directory containing the source code.
   - **`app`**
      A directory containing the api logic.
        - **`api`**
             A directory containing the API endpoints.
        - **`kpi_engine`**
             A directory containing the dynamic KPI calculation logic, for dynamic and real-time KPIs.
        - **`models`**
             A directory containing the request and response models, needed to communicate with the API.
        - **`services`**
             A directory containing the services that interact with the database and the KB.
        - **`utils`**
             A directory containing utility functions.
      - **`main.py`**
         A Python module that contains the main entry point of the application.
   - **`tests`**
      A directory containing the unit tests for the KPI Engine.
     - **`test_dynamic_calc.py`**
         A Python script that contains unit tests for the dynamic KPI calculation.
- **`.github`**
   A directory containing the GitHub Actions workflows, including CODEOWNERS.
- **`LICENSE`**
   A standard MIT license file.
- **`README.md`**
   A detailed README file containing information about the project, setup instructions, and other relevant details.
- **`Dockerfile`**
   A Dockerfile that contains that can be executed following the instructions as below.
- **`pyproject.toml`**
   Project configuration file with all libraries and tools.
- **`poetry.lock`**
   Poetry-generated lock file.


---

## Documentation

Check the [documentation](https://kreative-performative-individuals.github.io/KPI-Engine/) for more information.