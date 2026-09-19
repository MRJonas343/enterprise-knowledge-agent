variable "resource_prefix" {
  description = "Prefix for all resource names"
  type        = string
  default     = "knowledge-agent-344"
}

variable "region" {
  description = "Azure region for resources"
  type        = string
  default     = "canadacentral"
}

variable "resource_group_name" {
  description = "Name of the resource group created by this configuration"
  type        = string
  default     = "rg-knowledge-agent-344"
}

variable "sku_name" {
  description = "SKU tier for the Cognitive Services account"
  type        = string
  default     = "S0"
}

variable "model_name" {
  description = "Name of the model to deploy. Must be offered in the target region."
  type        = string
  default     = "gpt-5.4-mini"
}

variable "model_version" {
  description = "Version of the model to deploy. Must match the version available in the target region."
  type        = string
  default     = "2026-03-17"
}

variable "deployment_capacity" {
  description = "Rate limit for the deployment (requests per minute)"
  type        = number
  default     = 50
}

variable "user_object_id" {
  description = "Azure AD Object ID of the user to assign Foundry role. Defaults to current logged-in user."
  type        = string
  default     = ""
}

variable "storage_account_name" {
  description = "Globally unique storage account name. Lowercase letters and digits only, 3-24 characters, no hyphens. Cannot be changed after creation without recreating the account."
  type        = string
  default     = "knowledgeagent343"
}

variable "knowledge_container_name" {
  description = "Blob container that holds the enterprise knowledge documents. Mirrors the knowledge/ folder structure."
  type        = string
  default     = "enterprise-knowledge"
}

variable "search_service_name" {
  description = "Globally unique Azure AI Search service name. Becomes <name>.search.windows.net."
  type        = string
  default     = "knowledge-agent-343-search"
}

variable "embedding_model_name" {
  description = "Embedding model required by the Blob knowledge source for chunk vectorization."
  type        = string
  default     = "text-embedding-3-large"
}

variable "embedding_model_version" {
  description = "Version of the embedding model to deploy."
  type        = string
  default     = "1"
}

variable "embedding_deployment_capacity" {
  description = "Rate limit for the embedding deployment in thousands of tokens per minute."
  type        = number
  default     = 50
}
