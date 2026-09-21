resource "azurerm_log_analytics_workspace" "tracing" {
  name                            = "${var.resource_prefix}-law"
  location                        = azurerm_resource_group.main.location
  resource_group_name             = azurerm_resource_group.main.name
  sku                             = "PerGB2018"
  retention_in_days               = var.tracing_retention_days
  local_authentication_enabled    = false
  allow_resource_only_permissions = true

  tags = {
    purpose = "foundry-agent-tracing"
  }
}

resource "azurerm_application_insights" "tracing" {
  name                         = "${var.resource_prefix}-appi"
  location                     = azurerm_resource_group.main.location
  resource_group_name          = azurerm_resource_group.main.name
  application_type             = "web"
  workspace_id                 = azurerm_log_analytics_workspace.tracing.id
  retention_in_days            = var.tracing_retention_days
  local_authentication_enabled = false
  internet_ingestion_enabled   = true
  internet_query_enabled       = true

  tags = {
    purpose = "foundry-agent-tracing"
  }
}

resource "azurerm_role_assignment" "project_trace_publisher" {
  scope                = azurerm_application_insights.tracing.id
  role_definition_name = "Monitoring Metrics Publisher"
  principal_id         = azurerm_cognitive_account_project.ai_project.identity[0].principal_id
}

resource "azurerm_role_assignment" "user_trace_reader" {
  scope                = azurerm_application_insights.tracing.id
  role_definition_name = "Log Analytics Reader"
  principal_id         = local.user_principal_id
}

# Required to read GenAI content, which is where the tool calls appear.
resource "azurerm_role_assignment" "user_privileged_trace_reader" {
  scope                = azurerm_application_insights.tracing.id
  role_definition_name = "Privileged Monitoring Data Reader"
  principal_id         = local.user_principal_id
}

# Required for the gateway to emit its own telemetry, and not for reading it.
#
# Both tracing resources disable local authentication, so the connection string
# only identifies the target: it carries no key, and ingestion rejects a
# key-less request with 401. A token credential is the only way in, which is the
# same keyless rule the rest of this repository follows. Without this grant the
# gateway configures its exporters, exports nothing, and reports the failure
# only in a log line.
#
# Publish-only. It does not widen what can be read; the two reader roles above
# are unchanged.
resource "azurerm_role_assignment" "user_trace_publisher" {
  scope                = azurerm_application_insights.tracing.id
  role_definition_name = "Monitoring Metrics Publisher"
  principal_id         = local.user_principal_id
}
