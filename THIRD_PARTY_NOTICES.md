# Third-Party Notices

This file contains the licenses and notices for third-party software used in Context Graph Connector (CGC).

---

## Table of Contents

- [Machine Learning Models](#machine-learning-models)
- [Database Drivers](#database-drivers)
- [Vector Database Clients](#vector-database-clients)
- [Document Processing](#document-processing)
- [Data Handling](#data-handling)
- [Web Framework](#web-framework)
- [CLI Framework](#cli-framework)
- [MCP Protocol](#mcp-protocol)
- [Utilities](#utilities)
- [License Texts](#license-texts)

---

## Machine Learning Models

### GliNER

- **Package**: gliner
- **Source**: https://github.com/urchade/GLiNER
- **Model**: gliner_small-v2.1
- **License**: Apache License 2.0
- **Copyright**: Copyright (c) urchade

Used for named entity recognition in triplet extraction.

---

## Database Drivers

### SQLAlchemy

- **Package**: sqlalchemy
- **Version**: >=2.0
- **Source**: https://github.com/sqlalchemy/sqlalchemy
- **License**: MIT
- **Copyright**: Copyright 2005-2024 SQLAlchemy authors and contributors

The Python SQL toolkit and Object Relational Mapper.

### asyncpg

- **Package**: asyncpg
- **Source**: https://github.com/MagicStack/asyncpg
- **License**: Apache License 2.0
- **Copyright**: Copyright (c) 2016-present MagicStack Inc.

Async PostgreSQL driver for Python.

### aiomysql

- **Package**: aiomysql
- **Source**: https://github.com/aio-libs/aiomysql
- **License**: MIT
- **Copyright**: Copyright (c) aio-libs contributors

Async MySQL driver for Python.

### aiosqlite

- **Package**: aiosqlite
- **Source**: https://github.com/omnilib/aiosqlite
- **License**: MIT
- **Copyright**: Copyright (c) Amethyst Reese

Async SQLite driver for Python.

### pgvector

- **Package**: pgvector
- **Source**: https://github.com/pgvector/pgvector-python
- **License**: MIT
- **Copyright**: Copyright (c) Andrew Kane

PostgreSQL vector extension support for Python.

---

## Vector Database Clients

### Qdrant Client

- **Package**: qdrant-client
- **Version**: >=1.0
- **Source**: https://github.com/qdrant/qdrant-client
- **License**: Apache License 2.0
- **Copyright**: Copyright (c) Qdrant

Python client for Qdrant vector database.

### Pinecone Client

- **Package**: pinecone-client
- **Version**: >=3.0
- **Source**: https://github.com/pinecone-io/pinecone-python-client
- **License**: Apache License 2.0
- **Copyright**: Copyright (c) Pinecone Systems, Inc.

Python client for Pinecone vector database.

### PyMongo

- **Package**: pymongo
- **Version**: >=4.0
- **Source**: https://github.com/mongodb/mongo-python-driver
- **License**: Apache License 2.0
- **Copyright**: Copyright (c) MongoDB, Inc.

Python driver for MongoDB.

### Motor

- **Package**: motor
- **Source**: https://github.com/mongodb/motor
- **License**: Apache License 2.0
- **Copyright**: Copyright (c) MongoDB, Inc.

Async Python driver for MongoDB.

---

## Document Processing

### pypdf

- **Package**: pypdf
- **Version**: >=3.0
- **Source**: https://github.com/py-pdf/pypdf
- **License**: BSD 3-Clause License
- **Copyright**: Copyright (c) 2006-2008, Mathieu Fenniak; 2022, pypdf contributors

PDF parsing library for Python.

### pdfplumber

- **Package**: pdfplumber
- **Source**: https://github.com/jsvine/pdfplumber
- **License**: MIT
- **Copyright**: Copyright (c) 2015 Jeremy Singer-Vine

PDF extraction library with table support.

### python-docx

- **Package**: python-docx
- **Source**: https://github.com/python-openxml/python-docx
- **License**: MIT
- **Copyright**: Copyright (c) Steve Canny

Library for creating and updating Microsoft Word files.

### openpyxl

- **Package**: openpyxl
- **Source**: https://github.com/theorchard/openpyxl
- **License**: MIT
- **Copyright**: Copyright (c) 2010 openpyxl

Library for reading/writing Excel 2010+ files.

### xlrd

- **Package**: xlrd
- **Version**: >=2.0
- **Source**: https://github.com/python-excel/xlrd
- **License**: BSD 3-Clause License
- **Copyright**: Copyright (c) 2005-2022 Stephen John Machin, Lingfo Pty Ltd

Library for reading Excel files (.xls format).

---

## Data Handling

### Pydantic

- **Package**: pydantic
- **Version**: >=2.0
- **Source**: https://github.com/pydantic/pydantic
- **License**: MIT
- **Copyright**: Copyright (c) 2017-present Pydantic Services Inc. and individual contributors

Data validation using Python type annotations.

### Pandas

- **Package**: pandas
- **Source**: https://github.com/pandas-dev/pandas
- **License**: BSD 3-Clause License
- **Copyright**: Copyright (c) 2008-2011, AQR Capital Management, LLC, Lambda Foundry, Inc. and PyData Development Team

Data analysis and manipulation library.

### PyArrow

- **Package**: pyarrow
- **Source**: https://github.com/apache/arrow
- **License**: Apache License 2.0
- **Copyright**: Copyright (c) Apache Software Foundation

Cross-language development platform for in-memory data.

### aiofiles

- **Package**: aiofiles
- **Source**: https://github.com/Tinche/aiofiles
- **License**: Apache License 2.0
- **Copyright**: Copyright (c) Tin Tvrtkovic

Async file operations for Python.

---

## Web Framework

### FastAPI

- **Package**: fastapi
- **Version**: >=0.100
- **Source**: https://github.com/tiangolo/fastapi
- **License**: MIT
- **Copyright**: Copyright (c) 2018 Sebastián Ramírez

Modern, fast web framework for building APIs.

### Uvicorn

- **Package**: uvicorn
- **Source**: https://github.com/encode/uvicorn
- **License**: BSD 3-Clause License
- **Copyright**: Copyright (c) 2017-present, Encode OSS Ltd.

ASGI web server implementation for Python.

### Starlette

- **Package**: starlette (dependency of FastAPI)
- **Source**: https://github.com/encode/starlette
- **License**: BSD 3-Clause License
- **Copyright**: Copyright (c) 2018-present, Encode OSS Ltd.

Lightweight ASGI framework/toolkit.

---

## CLI Framework

### Typer

- **Package**: typer
- **Version**: >=0.9
- **Source**: https://github.com/tiangolo/typer
- **License**: MIT
- **Copyright**: Copyright (c) 2019 Sebastián Ramírez

Library for building CLI applications.

### Rich

- **Package**: rich
- **Source**: https://github.com/Textualize/rich
- **License**: MIT
- **Copyright**: Copyright (c) 2020 Will McGugan

Library for rich text and beautiful formatting in the terminal.

---

## MCP Protocol

### MCP (Model Context Protocol)

- **Package**: mcp
- **Version**: >=1.0
- **Source**: https://github.com/anthropics/anthropic-tools
- **License**: MIT
- **Copyright**: Copyright (c) Anthropic

Protocol for connecting AI models to external tools.

---

## Utilities

### python-dotenv

- **Package**: python-dotenv
- **Source**: https://github.com/theskumar/python-dotenv
- **License**: BSD 3-Clause License
- **Copyright**: Copyright (c) 2014, Saurabh Kumar

Read key-value pairs from .env files.

### structlog

- **Package**: structlog
- **Source**: https://github.com/hynek/structlog
- **License**: Apache License 2.0 OR MIT
- **Copyright**: Copyright (c) 2013 Hynek Schlawack

Structured logging for Python.

### HTTPX

- **Package**: httpx
- **Source**: https://github.com/encode/httpx
- **License**: BSD 3-Clause License
- **Copyright**: Copyright (c) 2019, Encode OSS Ltd.

Async HTTP client for Python.

---

## Object Storage

### Boto3

- **Package**: boto3
- **Source**: https://github.com/boto/boto3
- **License**: Apache License 2.0
- **Copyright**: Copyright (c) Amazon Web Services

AWS SDK for Python.

### aioboto3

- **Package**: aioboto3
- **Source**: https://github.com/terrycain/aioboto3
- **License**: Apache License 2.0
- **Copyright**: Copyright (c) Terry Cain

Async version of boto3.

---

## License Texts

### Apache License 2.0

```
                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

1. Definitions.

   "License" shall mean the terms and conditions for use, reproduction,
   and distribution as defined by Sections 1 through 9 of this document.

   "Licensor" shall mean the copyright owner or entity authorized by
   the copyright owner that is granting the License.

   "Legal Entity" shall mean the union of the acting entity and all
   other entities that control, are controlled by, or are under common
   control with that entity.

   "You" (or "Your") shall mean an individual or Legal Entity
   exercising permissions granted by this License.

   "Source" form shall mean the preferred form for making modifications.

   "Object" form shall mean any form resulting from mechanical
   transformation or translation of a Source form.

   "Work" shall mean the work of authorship made available under the License.

   "Derivative Works" shall mean any work that is based on the Work.

   "Contribution" shall mean any work of authorship submitted to the Licensor.

   "Contributor" shall mean Licensor and any Legal Entity on behalf of whom
   a Contribution has been received by Licensor.

2. Grant of Copyright License. Subject to the terms of this License, each
   Contributor grants to You a perpetual, worldwide, non-exclusive, no-charge,
   royalty-free, irrevocable copyright license to reproduce, prepare Derivative
   Works of, publicly display, publicly perform, sublicense, and distribute the
   Work and such Derivative Works in Source or Object form.

3. Grant of Patent License. Subject to the terms of this License, each
   Contributor grants to You a perpetual, worldwide, non-exclusive, no-charge,
   royalty-free, irrevocable patent license to make, have made, use, offer to
   sell, sell, import, and otherwise transfer the Work.

4. Redistribution. You may reproduce and distribute copies of the Work
   provided that You meet the following conditions:

   (a) You must give recipients a copy of this License; and
   (b) You must cause modified files to carry prominent notices; and
   (c) You must retain all copyright, patent, trademark notices; and
   (d) You must include any NOTICE file with the distribution.

5. Submission of Contributions. Any Contribution submitted for inclusion
   shall be under the terms of this License.

6. Trademarks. This License does not grant permission to use trade names,
   trademarks, service marks, or product names of the Licensor.

7. Disclaimer of Warranty. The Work is provided on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND.

8. Limitation of Liability. In no event shall any Contributor be liable
   for any damages arising from this License or use of the Work.

9. Accepting Warranty or Additional Liability. You may offer warranty,
   support, or indemnity obligations for a fee.

END OF TERMS AND CONDITIONS
```

### MIT License

```
MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### BSD 3-Clause License

```
BSD 3-Clause License

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

---

## Summary of Licenses Used

| License | Components |
|---------|------------|
| **Apache-2.0** | GliNER, asyncpg, Qdrant, Pinecone, PyMongo, Motor, PyArrow, aiofiles, structlog, Boto3, aioboto3 |
| **MIT** | SQLAlchemy, aiomysql, aiosqlite, pgvector, pdfplumber, python-docx, openpyxl, Pydantic, FastAPI, Typer, Rich, MCP |
| **BSD-3-Clause** | pypdf, xlrd, Pandas, Uvicorn, Starlette, python-dotenv, HTTPX |

All third-party components are used in compliance with their respective licenses. These licenses are all permissive open-source licenses that allow commercial use, modification, and distribution.

---

## Contact

If you have questions about licensing or third-party components used in CGC, please open an issue on the project repository.
