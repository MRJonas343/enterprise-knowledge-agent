# Foundry agent tracing.
#
# Foundry stores agent traces in Application Insights using OpenTelemetry
# semantic conventions, and Application Insights stores them in a Log Analytics
# workspace. Two resources, plus the role assignments that make the path keyless.
#
# Why local authentication is disabled on both:
#
# Foundry publishes traces with the project's managed identity, and Entra-only
# ingestion is what the service requires for that. Disabling local authentication
# is therefore not a preference here, it is the precondition. The project identity
# reaches Application Insights through the Monitoring Metrics Publisher role
# instead of a connection string.
#
# The *connection* that links Application Insights to the Foundry project is not
# an ARM resource this configuration can own, the same way the knowledge base MCP
# connection is not. It is created by a script against the project connections
# API, with authType ProjectManagedIdentity. See src/scripts/deploy_agent.py for
# the pattern already in use.

resource "azurerm_log_analytics_workspace" "tracing" {
  name                = "${var.resource_prefix}-law"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = var.tracing_retention_days

  local_authentication_enabled    = false
  allow_resource_only_permissions = true

  tags = {
    purpose = "foundry-agent-tracing"
  }
}

resource "azurerm_application_insights" "tracing" {
  name                = "${var.resource_prefix}-appi"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  application_type    = "web"
  workspace_id        = azurerm_log_analytics_workspace.tracing.id
  retention_in_days   = var.tracing_retention_days

  # Entra-only ingestion and query. Required for managed identity trace
  # publishing, and the reason no instrumentation key is used anywhere.
  local_authentication_enabled = false
  internet_ingestion_enabled   = true
  internet_query_enabled       = true

  tags = {
    purpose = "foundry-agent-tracing"
  }
}

# Trace ingestion.
#
# Foundry assigns this automatically when the connection is created from the
# portal. Declaring it here means a scripted connection produces the same result.
#
# The project identity is the one the Foundry documentation names for server-side
# trace emission. If traces do not appear after the connection exists, the
# account's own identity (azurerm_cognitive_account.ai_foundry) is the next
# candidate for this same assignment.
resource "azurerm_role_assignment" "project_trace_publisher" {
  scope                = azurerm_application_insights.tracing.id
  role_definition_name = "Monitoring Metrics Publisher"
  principal_id         = azurerm_cognitive_account_project.ai_project.identity[0].principal_id
}

# Reading traces.
#
# Required to see the traces in the Foundry portal at all. Scoped to the operator
# rather than granted broadly.
#
# If the underlying Log Analytics tables are ever marked protected, reading also
# needs "Privileged Monitoring Data Reader" on this same resource.
resource "azurerm_role_assignment" "user_trace_reader" {
  scope                = azurerm_application_insights.tracing.id
  role_definition_name = "Log Analytics Reader"
  principal_id         = local.user_principal_id
}
