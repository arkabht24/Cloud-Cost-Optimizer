# Azure Cost Insight React Dashboard

This React application is the dashboard-first UI for the local FastAPI service.

## Run locally

From the project root, start the API in one terminal:

```zsh
source .venv/bin/activate
zsh run_api.sh
```

In a second terminal, start the React UI:

```zsh
zsh run_web.sh
```

Open `http://127.0.0.1:5173`.

Use `demo-cost-lab` without Azure credentials. For a live Azure scope, sign in with `az login`, select a subscription ID and resource group, then load the workspace. Inventory uses the Azure CLI; cost and metric fields display as unavailable if the signed-in identity lacks the required access or the service does not expose the metric.
