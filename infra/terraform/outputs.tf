output "resource_group_name" {
  description = "Name of the Resource Group"
  value       = azurerm_resource_group.main.name
}

output "ai_foundry_endpoint" {
  description = "Foundry resource endpoint with no path. Use this as the knowledge source model resource URL."
  value       = "https://${azurerm_cognitive_account.ai_foundry.custom_subdomain_name}.services.ai.azure.com"
}

output "openai_endpoint" {
  description = "OpenAI-compatible inference endpoint (includes the /openai/v1 path). For chat clients, not for the knowledge source."
  value       = "https://${azurerm_cognitive_account.ai_foundry.custom_subdomain_name}.services.ai.azure.com/openai/v1"
}

output "llm_deployment_name" {
  description = "Name of the LLM model deployment"
  value       = azurerm_cognitive_deployment.llm_model.name
}

output "ai_foundry_name" {
  description = "Name of the AI Foundry hub"
  value       = azurerm_cognitive_account.ai_foundry.name
}

output "ai_project_name" {
  description = "Name of the AI Project"
  value       = azurerm_cognitive_account_project.ai_project.name
}

output "embedding_deployment_name" {
  description = "Embedding model deployment required by the Blob knowledge source"
  value       = azurerm_cognitive_deployment.embedding_model.name
}

output "storage_account_name" {
  description = "Storage account holding the enterprise knowledge documents"
  value       = azurerm_storage_account.knowledge.name
}

output "storage_account_id" {
  description = "Storage account resource ID, used as the keyless knowledge source connection string (ResourceId=...)"
  value       = azurerm_storage_account.knowledge.id
}

output "knowledge_container_name" {
  description = "Blob container used as the Foundry IQ knowledge source"
  value       = azurerm_storage_container.knowledge.name
}

output "search_endpoint" {
  description = "Azure AI Search endpoint that hosts the knowledge source and knowledge base"
  value       = "https://${azurerm_search_service.main.name}.search.windows.net"
}

output "application_insights_id" {
  description = "Application Insights resource ID. This is the connection target when linking tracing to the Foundry project."
  value       = azurerm_application_insights.tracing.id
}

output "application_insights_name" {
  description = "Application Insights resource name, shown in the Foundry portal once connected"
  value       = azurerm_application_insights.tracing.name
}

output "log_analytics_workspace_id" {
  description = "Log Analytics workspace that backs Application Insights and stores the agent traces"
  value       = azurerm_log_analytics_workspace.tracing.id
}

output "application_insights_connection_string" {
  description = "Application Insights connection string. The connections API requires it to identify the resource when the tracing connection is created, even though runtime ingestion authenticates with the project managed identity. Read it with terraform output -raw application_insights_connection_string."
  value       = azurerm_application_insights.tracing.connection_string
  sensitive   = true
}
