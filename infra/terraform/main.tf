# Resource Group
resource "azurerm_resource_group" "main" {
  name     = var.resource_group_name
  location = coalesce(var.region, "canadacentral")
}

locals {
  ai_foundry_name           = var.resource_prefix
  ai_project_name           = "${var.resource_prefix}-proj"
  llm_deployment_name       = "${var.resource_prefix}-llm-deploy"
  embedding_deployment_name = "${var.resource_prefix}-embed-deploy"
  user_principal_id = var.user_object_id != "" ? var.user_object_id : data.azurerm_client_config.current.object_id
}


# AI Foundry Hub (Cognitive Services account - AIServices kind)
resource "azurerm_cognitive_account" "ai_foundry" {
  name                = local.ai_foundry_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  kind                = "AIServices"
  sku_name            = var.sku_name

  identity {
    type = "SystemAssigned"
  }

  custom_subdomain_name     = local.ai_foundry_name
  project_management_enabled = true

  tags = {
    purpose = "ai-foundry-learning"
  }
}


# AI Project 
resource "azurerm_cognitive_account_project" "ai_project" {
  name                 = local.ai_project_name
  location             = azurerm_resource_group.main.location
  cognitive_account_id = azurerm_cognitive_account.ai_foundry.id

  identity {
    type = "SystemAssigned"
  }
}


# RBAC: Assign "Cognitive Services User" role to the specified user
data "azurerm_client_config" "current" {}

resource "azurerm_role_assignment" "foundry_user" {
  scope                = azurerm_cognitive_account.ai_foundry.id
  role_definition_name = "Cognitive Services User"
  principal_id         = local.user_principal_id
}

# LLM Model Deployment
resource "azurerm_cognitive_deployment" "llm_model" {
  name                = local.llm_deployment_name
  cognitive_account_id = azurerm_cognitive_account.ai_foundry.id

  sku {
    name     = "GlobalStandard"
    capacity = var.deployment_capacity
  }

  model {
    name    = var.model_name
    format  = "OpenAI"
    version = var.model_version
  }
}

# Embedding Model Deployment
resource "azurerm_cognitive_deployment" "embedding_model" {
  name                 = local.embedding_deployment_name
  cognitive_account_id = azurerm_cognitive_account.ai_foundry.id

  sku {
    name     = "GlobalStandard"
    capacity = var.embedding_deployment_capacity
  }

  model {
    name    = var.embedding_model_name
    format  = "OpenAI"
    version = var.embedding_model_version
  }
}
