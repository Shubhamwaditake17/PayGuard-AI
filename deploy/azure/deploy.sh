#!/usr/bin/env bash
# Deploy PayGuard AI to Azure Container Apps backed by Azure OpenAI.
# Prereqs: Azure CLI (`az login`), an Azure OpenAI resource with a chat deployment (e.g. gpt-4o-mini).
# NOTE: written from Azure docs; run it yourself and fix any CLI drift before relying on it.
set -euo pipefail

RG=${RG:-payguard-rg}
LOC=${LOC:-centralindia}
ACR=${ACR:-payguardacr$RANDOM}            # must be globally unique, lowercase
ENV=${ENV:-payguard-env}
APP=${APP:-payguard-ai}
: "${AZURE_OPENAI_ENDPOINT:?set AZURE_OPENAI_ENDPOINT}"
: "${AZURE_OPENAI_API_KEY:?set AZURE_OPENAI_API_KEY}"
: "${LLM_MODEL:?set LLM_MODEL to your Azure OpenAI deployment name}"

az group create -n "$RG" -l "$LOC"
az acr create -n "$ACR" -g "$RG" --sku Basic --admin-enabled true
az acr build -r "$ACR" -t payguard-ai:v1 .            # builds the repo Dockerfile in the cloud
az containerapp env create -n "$ENV" -g "$RG" -l "$LOC"

az containerapp create -n "$APP" -g "$RG" --environment "$ENV" \
  --image "$ACR.azurecr.io/payguard-ai:v1" \
  --registry-server "$ACR.azurecr.io" \
  --target-port 8000 --ingress external --min-replicas 0 --max-replicas 2 \
  --secrets aoai-key="$AZURE_OPENAI_API_KEY" \
  --env-vars LLM_PROVIDER=azure LLM_MODEL="$LLM_MODEL" \
             AZURE_OPENAI_ENDPOINT="$AZURE_OPENAI_ENDPOINT" AZURE_OPENAI_API_KEY=secretref:aoai-key

echo "Live at: https://$(az containerapp show -n "$APP" -g "$RG" --query properties.configuration.ingress.fqdn -o tsv)/docs"
echo "Tear down when done (avoid charges): az group delete -n $RG --yes"
