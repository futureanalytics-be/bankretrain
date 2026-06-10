FROM mcr.microsoft.com/azureml/openmpi4.1.0-ubuntu22.04

# Install Microsoft ODBC Driver 18 for SQL Server (OS-level, can't be done in conda)
RUN curl -sSL https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl -sSL https://packages.microsoft.com/config/ubuntu/22.04/prod.list \
       > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 unixodbc-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    "azure-identity>=1.15" \
    "azure-ai-ml>=1.16" \
    "azure-storage-blob>=12.19" \
    "azure-keyvault-secrets>=4.7" \
    "pandas>=2.0" \
    "numpy>=1.24" \
    "pyarrow>=13.0" \
    pyodbc \
    "scikit-learn>=1.3" \
    "lightgbm>=4.0" \
    "mlflow>=2.13,<3.0.0" \
    "azureml-mlflow" \
    "azure-search-documents>=11.4" \
    "matplotlib>=3.7" \
    "seaborn>=0.13"
