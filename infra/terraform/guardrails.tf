resource "azapi_resource" "guardrail" {
  type      = "Microsoft.CognitiveServices/accounts/raiPolicies@2024-10-01"
  name      = "strict-guardrail"
  parent_id = azurerm_cognitive_account.ai_foundry.id

  body = {
    properties = {
      basePolicyName = "Microsoft.DefaultV2"
      mode           = "Blocking"
      contentFilters = [
        { name = "Hate", source = "Prompt", enabled = true, blocking = true, severityThreshold = "Medium" },
        { name = "Hate", source = "Completion", enabled = true, blocking = true, severityThreshold = "Medium" },
        { name = "Sexual", source = "Prompt", enabled = true, blocking = true, severityThreshold = "Medium" },
        { name = "Sexual", source = "Completion", enabled = true, blocking = true, severityThreshold = "Medium" },
        { name = "Selfharm", source = "Prompt", enabled = true, blocking = true, severityThreshold = "Medium" },
        { name = "Selfharm", source = "Completion", enabled = true, blocking = true, severityThreshold = "Medium" },
        { name = "Violence", source = "Prompt", enabled = true, blocking = true, severityThreshold = "Medium" },
        { name = "Violence", source = "Completion", enabled = true, blocking = true, severityThreshold = "Medium" },
        { name = "Jailbreak", source = "Prompt", enabled = true, blocking = true, severityThreshold = null },
        { name = "Indirect Attack", source = "Prompt", enabled = true, blocking = true, severityThreshold = null },
        { name = "Profanity", source = "Prompt", enabled = true, blocking = true, severityThreshold = null },
        { name = "Profanity", source = "Completion", enabled = true, blocking = true, severityThreshold = null },
        { name = "Protected Material Text", source = "Prompt", enabled = true, blocking = true, severityThreshold = null },
        { name = "Protected Material Text", source = "Completion", enabled = true, blocking = true, severityThreshold = null },
        { name = "Protected Material Code", source = "Prompt", enabled = true, blocking = true, severityThreshold = null },
        { name = "Protected Material Code", source = "Completion", enabled = true, blocking = true, severityThreshold = null },
      ]
    }
  }
}
