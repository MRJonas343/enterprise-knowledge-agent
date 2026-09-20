# Storage Account
resource "azurerm_storage_account" "knowledge" {
  name                            = var.storage_account_name
  resource_group_name             = azurerm_resource_group.main.name
  location                        = azurerm_resource_group.main.location
  account_kind                    = "StorageV2"
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = false
  default_to_oauth_authentication = true

  blob_properties {
    versioning_enabled = true
  }

  tags = {
    purpose = "enterprise-knowledge-source"
  }
}

# Knowledge Container
resource "azurerm_storage_container" "knowledge" {
  name                  = var.knowledge_container_name
  storage_account_id    = azurerm_storage_account.knowledge.id
  container_access_type = "private"
}


# RBAC: Storage
resource "azurerm_role_assignment" "user_blob_contributor" {
  scope                = azurerm_storage_account.knowledge.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = local.user_principal_id
}

resource "azurerm_role_assignment" "search_blob_reader" {
  scope                = azurerm_storage_account.knowledge.id
  role_definition_name = "Storage Blob Data Reader"
  principal_id         = azurerm_search_service.main.identity[0].principal_id
}

# Lets the gateway mint short-lived user-delegation SAS links so a citation can
# be opened. The account is keyless, so there is no account key to sign a service
# SAS with; a user-delegation key is the only route, and generating one requires
# this role rather than data-plane read access.
resource "azurerm_role_assignment" "gateway_blob_delegator" {
  scope                = azurerm_storage_account.knowledge.id
  role_definition_name = "Storage Blob Delegator"
  principal_id         = local.user_principal_id
}
