# Azure AI Search
resource "azurerm_search_service" "main" {
  name                         = var.search_service_name
  resource_group_name          = azurerm_resource_group.main.name
  location                     = azurerm_resource_group.main.location
  sku                          = "basic"
  semantic_search_sku          = "free"
  local_authentication_enabled = false

  identity {
    type = "SystemAssigned"
  }

  tags = {
    purpose = "foundry-iq-retrieval"
  }
}

# RBAC: Search and model access
resource "azurerm_role_assignment" "search_foundry_user" {
  scope                = azurerm_cognitive_account.ai_foundry.id
  role_definition_name = "Cognitive Services User"
  principal_id         = azurerm_search_service.main.identity[0].principal_id
}

resource "azurerm_role_assignment" "user_search_contributor" {
  scope                = azurerm_search_service.main.id
  role_definition_name = "Search Service Contributor"
  principal_id         = local.user_principal_id
}

resource "azurerm_role_assignment" "user_search_index_data" {
  scope                = azurerm_search_service.main.id
  role_definition_name = "Search Index Data Contributor"
  principal_id         = local.user_principal_id
}

resource "azurerm_role_assignment" "project_search_index_reader" {
  scope                = azurerm_search_service.main.id
  role_definition_name = "Search Index Data Reader"
  principal_id         = azurerm_cognitive_account_project.ai_project.identity[0].principal_id
}
