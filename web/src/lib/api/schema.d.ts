export interface paths {
  "/api/v1/approvals": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** List Pending */
    get: operations["list_pending_api_v1_approvals_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/configs": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** List Configs */
    get: operations["list_configs_api_v1_configs_get"];
    put?: never;
    /** Create Config */
    post: operations["create_config_api_v1_configs_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/configs/{config_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get Config */
    get: operations["get_config_api_v1_configs__config_id__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/configs/{config_id}/teams": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List Teams Using
     * @description Times que usam o agente: publicar o agente muda o comportamento deles (ADR-0011).
     */
    get: operations["list_teams_using_api_v1_configs__config_id__teams_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/configs/{config_id}/versions": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** List Versions */
    get: operations["list_versions_api_v1_configs__config_id__versions_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/configs/{config_id}/publish": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Publish Draft */
    post: operations["publish_draft_api_v1_configs__config_id__publish_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/configs/{config_id}/rollback": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Rollback */
    post: operations["rollback_api_v1_configs__config_id__rollback_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/configs/{config_id}/draft": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    /** Save Draft */
    put: operations["save_draft_api_v1_configs__config_id__draft_put"];
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/integrations": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** List Integrations */
    get: operations["list_integrations_api_v1_integrations_get"];
    put?: never;
    /** Issue */
    post: operations["issue_api_v1_integrations_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/integrations/{integration_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    /** Revoke */
    delete: operations["revoke_api_v1_integrations__integration_id__delete"];
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/knowledge-bases/embedders": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** List Embedders */
    get: operations["list_embedders_api_v1_knowledge_bases_embedders_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/knowledge-bases": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** List Bases */
    get: operations["list_bases_api_v1_knowledge_bases_get"];
    put?: never;
    /** Create Base */
    post: operations["create_base_api_v1_knowledge_bases_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/knowledge-bases/{base_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get Base */
    get: operations["get_base_api_v1_knowledge_bases__base_id__get"];
    /** Update Base */
    put: operations["update_base_api_v1_knowledge_bases__base_id__put"];
    post?: never;
    /** Delete Base */
    delete: operations["delete_base_api_v1_knowledge_bases__base_id__delete"];
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/knowledge-bases/{base_id}/search": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Search
     * @description Trechos que o agente receberia para a pergunta, sem rodar o agente.
     */
    post: operations["search_api_v1_knowledge_bases__base_id__search_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/knowledge-bases/{base_id}/contents": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** List Contents */
    get: operations["list_contents_api_v1_knowledge_bases__base_id__contents_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/knowledge-bases/{base_id}/contents/{content_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get Content */
    get: operations["get_content_api_v1_knowledge_bases__base_id__contents__content_id__get"];
    put?: never;
    post?: never;
    /** Delete Content */
    delete: operations["delete_content_api_v1_knowledge_bases__base_id__contents__content_id__delete"];
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/knowledge-bases/{base_id}/contents/file": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Upload File */
    post: operations["upload_file_api_v1_knowledge_bases__base_id__contents_file_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/knowledge-bases/{base_id}/contents/url": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Add Url */
    post: operations["add_url_api_v1_knowledge_bases__base_id__contents_url_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/knowledge-bases/{base_id}/contents/text": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Add Text */
    post: operations["add_text_api_v1_knowledge_bases__base_id__contents_text_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/models/capabilities": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** List Capabilities */
    get: operations["list_capabilities_api_v1_models_capabilities_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/linter": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Run Linter */
    post: operations["run_linter_api_v1_linter_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/mcp-servers": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** List Servers */
    get: operations["list_servers_api_v1_mcp_servers_get"];
    put?: never;
    /** Create Server */
    post: operations["create_server_api_v1_mcp_servers_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/mcp-servers/{server_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get Server */
    get: operations["get_server_api_v1_mcp_servers__server_id__get"];
    /** Update Server */
    put: operations["update_server_api_v1_mcp_servers__server_id__put"];
    post?: never;
    /** Delete Server */
    delete: operations["delete_server_api_v1_mcp_servers__server_id__delete"];
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/mcp-servers/{server_id}/discover": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Discover
     * @description Testa a conexão e salva o retrato das tools do servidor.
     *
     *     Liberado para quem edita agentes (não só owner): não muda URL nem
     *     credencial, só atualiza a lista de tools que o painel oferece.
     */
    post: operations["discover_api_v1_mcp_servers__server_id__discover_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/metrics/summary": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get Summary */
    get: operations["get_summary_api_v1_metrics_summary_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/metrics/by-agent": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get By Agent */
    get: operations["get_by_agent_api_v1_metrics_by_agent_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/metrics/timeseries": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get Timeseries */
    get: operations["get_timeseries_api_v1_metrics_timeseries_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/configs/{config_id}/metrics": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get Metrics */
    get: operations["get_metrics_api_v1_configs__config_id__metrics_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/configs/{config_id}/runs": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** List Runs */
    get: operations["list_runs_api_v1_configs__config_id__runs_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/runs/{run_id}/trace": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get Run Trace */
    get: operations["get_run_trace_api_v1_runs__run_id__trace_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/usage/rollup": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get Rollup */
    get: operations["get_rollup_api_v1_usage_rollup_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/users": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** List Users */
    get: operations["list_users_api_v1_users_get"];
    put?: never;
    /** Create User */
    post: operations["create_user_api_v1_users_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/users/{user_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    /** Delete User */
    delete: operations["delete_user_api_v1_users__user_id__delete"];
    options?: never;
    head?: never;
    /** Update User */
    patch: operations["update_user_api_v1_users__user_id__patch"];
    trace?: never;
  };
  "/api/v1/users/{user_id}/password": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Reset Password */
    post: operations["reset_password_api_v1_users__user_id__password_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/me": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Me
     * @description Quem está logado. Token de integração não tem usuário: volta só o sub.
     */
    get: operations["me_api_v1_me_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/auth/login": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Login */
    post: operations["login_api_v1_auth_login_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/auth/logout": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Logout
     * @description Revoga o token da sessão: o RevocationMiddleware passa a recusá-lo até expirar.
     */
    post: operations["logout_api_v1_auth_logout_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/auth/users": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Create User */
    post: operations["create_user_api_v1_auth_users_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
}
export type webhooks = Record<string, never>;
export interface components {
  schemas: {
    /** AgentBreakdownItem */
    AgentBreakdownItem: {
      /**
       * Agent Config Id
       * Format: uuid
       */
      agent_config_id: string;
      /** Agent Name */
      agent_name: string;
      /** Total Runs */
      total_runs: number;
      /** Error Rate */
      error_rate: number;
      /**
       * Blocked Runs
       * @default 0
       */
      blocked_runs: number;
      /** Total Tokens */
      total_tokens: number;
      /** Total Cost */
      total_cost: number | null;
    };
    /** AgentConfigDetail */
    AgentConfigDetail: {
      /**
       * Id
       * Format: uuid
       */
      id: string;
      kind: components["schemas"]["ConfigKind"];
      /** Name */
      name: string;
      /** Description */
      description: string;
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /**
       * Updated At
       * Format: date-time
       */
      updated_at: string;
      current_version: components["schemas"]["AgentConfigVersionSummary"] | null;
      draft_version: components["schemas"]["AgentConfigVersionSummary"] | null;
      payload: components["schemas"]["ConfigPayload"] | null;
    };
    /** AgentConfigPage */
    AgentConfigPage: {
      /** Items */
      items: components["schemas"]["AgentConfigResponse"][];
      /** Total */
      total: number;
      /** Page */
      page: number;
      /** Page Size */
      page_size: number;
    };
    /** AgentConfigResponse */
    AgentConfigResponse: {
      /**
       * Id
       * Format: uuid
       */
      id: string;
      kind: components["schemas"]["ConfigKind"];
      /** Name */
      name: string;
      /** Description */
      description: string;
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /**
       * Updated At
       * Format: date-time
       */
      updated_at: string;
      current_version: components["schemas"]["AgentConfigVersionSummary"] | null;
      draft_version: components["schemas"]["AgentConfigVersionSummary"] | null;
    };
    /** AgentConfigVersionDetail */
    AgentConfigVersionDetail: {
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Version Number */
      version_number: number;
      /** Label */
      label: string | null;
      status: components["schemas"]["ConfigPayloadStatus"];
      /** Author */
      author: string;
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      payload: components["schemas"]["ConfigPayload"];
    };
    /** AgentConfigVersionSummary */
    AgentConfigVersionSummary: {
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Version Number */
      version_number: number;
      /** Label */
      label: string | null;
      status: components["schemas"]["ConfigPayloadStatus"];
      /** Author */
      author: string;
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
    };
    /** AgentMetricsResponse */
    AgentMetricsResponse: {
      /** Total Runs */
      total_runs: number;
      /** Error Rate */
      error_rate: number;
      /** P50 Ms */
      p50_ms: number | null;
      /** P95 Ms */
      p95_ms: number | null;
      /** Period Days */
      period_days: number;
      /**
       * Blocked Runs
       * @default 0
       */
      blocked_runs: number;
      /**
       * Blocked By
       * @default {}
       */
      blocked_by: {
        [key: string]: number;
      };
    };
    /** AgentRunResponse */
    AgentRunResponse: {
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /**
       * Agent Config Id
       * Format: uuid
       */
      agent_config_id: string;
      /** User Id */
      user_id: string;
      /** Run Id */
      run_id: string | null;
      /** Status */
      status: string;
      /** Duration Ms */
      duration_ms: number | null;
      /** Error */
      error: string | null;
      /** Blocked By */
      blocked_by?: string | null;
      /** Steps */
      steps?: number | null;
      /** Total Tokens */
      total_tokens?: number | null;
      /** Cost */
      cost?: number | null;
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
    };
    /** ApprovalItem */
    ApprovalItem: {
      /** Run Id */
      run_id: string;
      /**
       * Agent Id
       * Format: uuid
       */
      agent_id: string;
      /** Agent Name */
      agent_name: string;
      /** Session Id */
      session_id: string | null;
      /** User Id */
      user_id: string;
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /** Tools */
      tools: components["schemas"]["PendingTool"][];
    };
    /** Body_upload_file_api_v1_knowledge_bases__base_id__contents_file_post */
    Body_upload_file_api_v1_knowledge_bases__base_id__contents_file_post: {
      /** File */
      file: string;
      /** Name */
      name?: string | null;
    };
    /** CapabilityFlags */
    CapabilityFlags: {
      /**
       * Extended Thinking
       * @default false
       */
      extended_thinking: boolean;
      /**
       * Structured Output
       * @default false
       */
      structured_output: boolean;
      /**
       * Vision
       * @default false
       */
      vision: boolean;
    };
    /** ConditionNode */
    ConditionNode: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      type: "condition";
      /** Name */
      name: string;
      rule: components["schemas"]["WorkflowRule"];
      /** Steps */
      steps: (
        | components["schemas"]["StepNode"]
        | components["schemas"]["ParallelNode"]
        | components["schemas"]["ConditionNode"]
        | components["schemas"]["LoopNode"]
      )[];
      /** Else Steps */
      else_steps?: (
        | components["schemas"]["StepNode"]
        | components["schemas"]["ParallelNode"]
        | components["schemas"]["ConditionNode"]
        | components["schemas"]["LoopNode"]
      )[];
    };
    /**
     * ConfigKind
     * @enum {string}
     */
    ConfigKind: "agent" | "team" | "workflow";
    /**
     * ConfigPayload
     * @description Payload JSONB de uma versão de configuração.
     *
     *     schema_version é guardado dentro do payload para permitir migrações
     *     de formato sem alterar a coluna — a lógica de upgrade fica no código,
     *     não no schema do banco.
     *
     *     v1 → v2: `tools: list[str]`, que nunca chegou ao agente, dá lugar a
     *     `mcp_servers`. Versões v1 gravadas são convertidas na leitura.
     */
    ConfigPayload: {
      /**
       * Schema Version
       * @default 2
       * @constant
       */
      schema_version: 2;
      /** Model Id */
      model_id?: string | null;
      instructions?: components["schemas"]["InstructionSections"];
      /** Mcp Servers */
      mcp_servers?: components["schemas"]["McpServerBinding"][];
      /** Knowledge */
      knowledge?: components["schemas"]["KnowledgeBinding"][];
      guardrails?: components["schemas"]["GuardrailSettings"];
      capabilities?: components["schemas"]["CapabilityFlags"];
      /** Metadata */
      metadata?: {
        [key: string]: unknown;
      };
      team?: components["schemas"]["TeamSettings"] | null;
      workflow?: components["schemas"]["WorkflowSettings"] | null;
    };
    /**
     * ConfigPayloadStatus
     * @enum {string}
     */
    ConfigPayloadStatus: "draft" | "published";
    /** CreateConfigInput */
    CreateConfigInput: {
      /** Name */
      name: string;
      /** Description */
      description: string;
      /** @default agent */
      kind: components["schemas"]["ConfigKind"];
    };
    /** CreateUserInput */
    CreateUserInput: {
      /**
       * Email
       * Format: email
       */
      email: string;
      /** Password */
      password: string;
      /** @default viewer */
      role: components["schemas"]["UserRole"];
    };
    /** DailyMetricsPoint */
    DailyMetricsPoint: {
      /**
       * Date
       * Format: date
       */
      date: string;
      /** Total Runs */
      total_runs: number;
      /** Error Count */
      error_count: number;
      /**
       * Blocked Count
       * @default 0
       */
      blocked_count: number;
      /** P50 Ms */
      p50_ms: number | null;
      /** P95 Ms */
      p95_ms: number | null;
      /** Total Tokens */
      total_tokens: number;
      /** Total Cost */
      total_cost: number | null;
    };
    /** DraftInput */
    DraftInput: {
      /** Name */
      name: string;
      /** Description */
      description: string;
      payload: components["schemas"]["ConfigPayload"];
    };
    /** EmbedderInfo */
    EmbedderInfo: {
      /**
       * Name
       * @enum {string}
       */
      name: "voyage" | "openai";
      /** Model */
      model: string;
      /** Dimensions */
      dimensions: number;
      /** Configured */
      configured: boolean;
      /** Default */
      default: boolean;
    };
    /** GlobalMetricsSummary */
    GlobalMetricsSummary: {
      /** Total Runs */
      total_runs: number;
      /** Error Rate */
      error_rate: number;
      /**
       * Blocked Runs
       * @default 0
       */
      blocked_runs: number;
      /**
       * Blocked By
       * @default {}
       */
      blocked_by: {
        [key: string]: number;
      };
      /** P50 Ms */
      p50_ms: number | null;
      /** P95 Ms */
      p95_ms: number | null;
      /** Total Tokens */
      total_tokens: number;
      /** Total Cost */
      total_cost: number | null;
      /**
       * Embedding Tokens
       * @default 0
       */
      embedding_tokens: number;
      /** Embedding Cost */
      embedding_cost?: number | null;
      /** Period Days */
      period_days: number;
    };
    /**
     * GuardrailSettings
     * @description Regras de entrada do agente (ADR-0013). Tudo desligado por padrão.
     */
    GuardrailSettings: {
      pii?: components["schemas"]["PiiRule"];
      /**
       * Prompt Injection
       * @default false
       */
      prompt_injection: boolean;
      /** Injection Extra Terms */
      injection_extra_terms?: string[];
      /** Blocked Topics */
      blocked_topics?: string[];
      /** Max Input Chars */
      max_input_chars?: number | null;
      /**
       * Moderation
       * @default false
       */
      moderation: boolean;
      output?: components["schemas"]["OutputRule"];
      /**
       * Blocked Message
       * @default Não posso ajudar com essa mensagem por aqui.
       */
      blocked_message: string;
    };
    /** HTTPValidationError */
    HTTPValidationError: {
      /** Detail */
      detail?: components["schemas"]["ValidationError"][];
    };
    /** InstructionSections */
    InstructionSections: {
      /**
       * Persona
       * @default
       */
      persona: string;
      /**
       * Situation
       * @default
       */
      situation: string;
      /**
       * Tone
       * @default
       */
      tone: string;
      /**
       * Objective
       * @default
       */
      objective: string;
      /**
       * Guardrails
       * @default
       */
      guardrails: string;
    };
    /** IntegrationInput */
    IntegrationInput: {
      /** Name */
      name: string;
      /** Agent Ids */
      agent_ids?: string[];
      /** Team Ids */
      team_ids?: string[];
      /**
       * Expires In Days
       * @default 30
       */
      expires_in_days: number;
    };
    /** IntegrationResponse */
    IntegrationResponse: {
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Name */
      name: string;
      /** Agent Ids */
      agent_ids: string[];
      /** Team Ids */
      team_ids: string[];
      /** Created By */
      created_by: string;
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /**
       * Expires At
       * Format: date-time
       */
      expires_at: string;
      /** Revoked At */
      revoked_at: string | null;
    };
    /** IssuedIntegration */
    IssuedIntegration: {
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Name */
      name: string;
      /** Agent Ids */
      agent_ids: string[];
      /** Team Ids */
      team_ids: string[];
      /** Created By */
      created_by: string;
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /**
       * Expires At
       * Format: date-time
       */
      expires_at: string;
      /** Revoked At */
      revoked_at: string | null;
      /** Token */
      token: string;
      /** Mcp Url */
      mcp_url: string | null;
    };
    /** KnowledgeBaseCreate */
    KnowledgeBaseCreate: {
      /** Name */
      name: string;
      /**
       * Description
       * @description Usada pelo agente para decidir quando buscar
       * @default
       */
      description: string;
      /**
       * Chunk Size
       * @description Vale para novas ingestões
       * @default 2000
       */
      chunk_size: number;
      /**
       * Slug
       * @description Nome da tool de busca; não muda depois
       */
      slug: string;
      /**
       * Embedder
       * @description Vazio usa KNOWLEDGE_DEFAULT_EMBEDDER; não muda depois
       */
      embedder?: ("voyage" | "openai") | null;
    };
    /** KnowledgeBaseResponse */
    KnowledgeBaseResponse: {
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Name */
      name: string;
      /** Slug */
      slug: string;
      /** Description */
      description: string;
      /** Embedder */
      embedder: string;
      /** Embedder Model */
      embedder_model: string;
      /** Dimensions */
      dimensions: number;
      /** Chunk Size */
      chunk_size: number;
      /**
       * Embedding Tokens
       * @default 0
       */
      embedding_tokens: number;
      /** Embedding Cost */
      embedding_cost?: number | null;
      /** Updated By */
      updated_by: string;
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /**
       * Updated At
       * Format: date-time
       */
      updated_at: string;
    };
    /** KnowledgeBaseUpdate */
    KnowledgeBaseUpdate: {
      /** Name */
      name: string;
      /**
       * Description
       * @description Usada pelo agente para decidir quando buscar
       * @default
       */
      description: string;
      /**
       * Chunk Size
       * @description Vale para novas ingestões
       * @default 2000
       */
      chunk_size: number;
    };
    /**
     * KnowledgeBinding
     * @description Base de conhecimento que o agente consulta (ADR-0012). A base em si não é versionada.
     */
    KnowledgeBinding: {
      /**
       * Base Id
       * Format: uuid
       */
      base_id: string;
      /**
       * Max Results
       * @default 5
       */
      max_results: number;
    };
    /** KnowledgeContentResponse */
    KnowledgeContentResponse: {
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /**
       * Base Id
       * Format: uuid
       */
      base_id: string;
      /** Name */
      name: string;
      /**
       * Source Type
       * @enum {string}
       */
      source_type: "file" | "url" | "text";
      /** Source */
      source: string;
      /** Extension */
      extension: string;
      /** Size Bytes */
      size_bytes: number;
      /**
       * Status
       * @enum {string}
       */
      status: "processing" | "completed" | "failed";
      /** Status Message */
      status_message: string | null;
      /** Chunk Count */
      chunk_count: number;
      /** Created By */
      created_by: string;
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /**
       * Updated At
       * Format: date-time
       */
      updated_at: string;
    };
    /** LintWarning */
    LintWarning: {
      /** Section */
      section: string;
      /** Code */
      code: string;
      /** Message */
      message: string;
    };
    /** LoginInput */
    LoginInput: {
      /**
       * Email
       * Format: email
       */
      email: string;
      /** Password */
      password: string;
    };
    /** LoopNode */
    LoopNode: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      type: "loop";
      /** Name */
      name: string;
      /** Steps */
      steps: (
        | components["schemas"]["StepNode"]
        | components["schemas"]["ParallelNode"]
        | components["schemas"]["ConditionNode"]
        | components["schemas"]["LoopNode"]
      )[];
      /**
       * Max Iterations
       * @default 3
       */
      max_iterations: number;
      until?: components["schemas"]["WorkflowRule"] | null;
    };
    /**
     * McpServerBinding
     * @description Servidor MCP que o agente usa e quais tools dele (ADR-0010).
     */
    McpServerBinding: {
      /**
       * Server Id
       * Format: uuid
       */
      server_id: string;
      /** Tools */
      tools?: string[] | null;
      /** Require Confirmation */
      require_confirmation?: string[];
    };
    /** McpServerInput */
    McpServerInput: {
      /** Name */
      name: string;
      /**
       * Slug
       * @description Prefixo das tools deste servidor
       */
      slug: string;
      /**
       * Url
       * Format: uri
       */
      url: string;
      /**
       * Timeout Seconds
       * @default 30
       */
      timeout_seconds: number;
      /** Headers */
      headers?: {
        [key: string]: string;
      } | null;
    };
    /** McpServerResponse */
    McpServerResponse: {
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Name */
      name: string;
      /** Slug */
      slug: string;
      /** Url */
      url: string;
      /** Timeout Seconds */
      timeout_seconds: number;
      /** Header Names */
      header_names: string[];
      /** Tools */
      tools: components["schemas"]["McpToolInfo"][] | null;
      /** Tools Discovered At */
      tools_discovered_at: string | null;
      /** Updated By */
      updated_by: string;
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /**
       * Updated At
       * Format: date-time
       */
      updated_at: string;
    };
    /** McpToolInfo */
    McpToolInfo: {
      /** Name */
      name: string;
      /** Description */
      description?: string | null;
      /** Input Schema */
      input_schema?: {
        [key: string]: unknown;
      };
    };
    /** MeResponse */
    MeResponse: {
      /** Id */
      id: string;
      /** Email */
      email: string | null;
      role: components["schemas"]["UserRole"] | null;
    };
    /**
     * OutputRule
     * @description Validação da resposta. No stream o texto já saiu quando ela roda (ADR-0013).
     */
    OutputRule: {
      /**
       * Pii
       * @default false
       */
      pii: boolean;
      /** Pii Types */
      pii_types?: ("cpf" | "cnpj" | "cartao" | "email" | "telefone")[];
      /** Blocked Terms */
      blocked_terms?: string[];
    };
    /** ParallelNode */
    ParallelNode: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      type: "parallel";
      /** Name */
      name: string;
      /** Branches */
      branches: components["schemas"]["StepNode"][];
    };
    /** PendingTool */
    PendingTool: {
      /** Tool Call Id */
      tool_call_id: string | null;
      /** Tool Name */
      tool_name: string | null;
      /** Tool Args */
      tool_args: {
        [key: string]: unknown;
      } | null;
      /** Tool Execution */
      tool_execution: {
        [key: string]: unknown;
      };
    };
    /** PiiRule */
    PiiRule: {
      /**
       * Mode
       * @default off
       * @enum {string}
       */
      mode: "off" | "mask" | "block";
      /** Types */
      types?: ("cpf" | "cnpj" | "cartao" | "email" | "telefone")[];
    };
    /** ResetPasswordInput */
    ResetPasswordInput: {
      /** Password */
      password: string;
    };
    /** RollbackInput */
    RollbackInput: {
      /**
       * Version Id
       * Format: uuid
       */
      version_id: string;
    };
    /** RollupItem */
    RollupItem: {
      /**
       * Agent Config Id
       * Format: uuid
       */
      agent_config_id: string;
      /** Period */
      period: string;
      /** Run Count */
      run_count: number;
      /** Input Tokens */
      input_tokens: number;
      /** Output Tokens */
      output_tokens: number;
      /** Total Tokens */
      total_tokens: number;
      /** Cost */
      cost: number | null;
      /**
       * Embedding Tokens
       * @default 0
       */
      embedding_tokens: number;
      /** Embedding Cost */
      embedding_cost?: number | null;
    };
    /** RunTrace */
    RunTrace: {
      /** Trace Id */
      trace_id: string;
      /** Run Id */
      run_id: string | null;
      /** Status */
      status: string;
      /** Duration */
      duration: string;
      /** Total Spans */
      total_spans: number;
      /** Error Count */
      error_count: number;
      /** Tree */
      tree: components["schemas"]["TraceSpan"][];
    };
    /** RunsPage */
    RunsPage: {
      /** Items */
      items: components["schemas"]["AgentRunResponse"][];
      /** Total */
      total: number;
      /** Page */
      page: number;
      /** Page Size */
      page_size: number;
    };
    /** SearchHit */
    SearchHit: {
      /** Content Id */
      content_id: string | null;
      /** Content Name */
      content_name: string | null;
      /** Source */
      source: string | null;
      /** Text */
      text: string;
      /**
       * Score
       * @description Combina similaridade e full-text, de 0 a 1
       */
      score: number | null;
    };
    /** SearchInput */
    SearchInput: {
      /** Query */
      query: string;
      /**
       * Max Results
       * @default 5
       */
      max_results: number;
    };
    /** StepNode */
    StepNode: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      type: "step";
      /** Name */
      name: string;
      /** Agent Id */
      agent_id?: string | null;
      /** Team Id */
      team_id?: string | null;
      /** Version Id */
      version_id?: string | null;
      /**
       * On Error
       * @default stop
       * @enum {string}
       */
      on_error: "stop" | "continue";
      /**
       * Max Retries
       * @default 0
       */
      max_retries: number;
    };
    /** TeamMember */
    TeamMember: {
      /**
       * Agent Id
       * Format: uuid
       */
      agent_id: string;
      /** Version Id */
      version_id?: string | null;
    };
    /**
     * TeamSettings
     * @description Seção de time do payload. Só existe em config de kind=team.
     */
    TeamSettings: {
      /**
       * Mode
       * @default coordinate
       * @enum {string}
       */
      mode: "coordinate" | "route" | "broadcast" | "tasks";
      /** Members */
      members: components["schemas"]["TeamMember"][];
      /**
       * Max Iterations
       * @default 10
       */
      max_iterations: number;
      /**
       * Share Member Interactions
       * @default false
       */
      share_member_interactions: boolean;
    };
    /** TextContentInput */
    TextContentInput: {
      /** Name */
      name: string;
      /** Text */
      text: string;
    };
    /** TokenResponse */
    TokenResponse: {
      /** Access Token */
      access_token: string;
      /**
       * Token Type
       * @default bearer
       */
      token_type: string;
    };
    /** TraceSpan */
    TraceSpan: {
      /** Id */
      id: string;
      /** Name */
      name: string;
      /** Type */
      type: string;
      /** Duration */
      duration: string;
      /** Status */
      status: string;
      /**
       * Start Time
       * Format: date-time
       */
      start_time: string;
      /**
       * End Time
       * Format: date-time
       */
      end_time: string;
      /** Input */
      input?: string | null;
      /** Output */
      output?: string | null;
      /** Error */
      error?: string | null;
      /** Spans */
      spans?: components["schemas"]["TraceSpan"][];
    };
    /** UpdateUserInput */
    UpdateUserInput: {
      role?: components["schemas"]["UserRole"] | null;
      /** Is Active */
      is_active?: boolean | null;
    };
    /** UrlContentInput */
    UrlContentInput: {
      /**
       * Url
       * Format: uri
       */
      url: string;
      /** Name */
      name?: string | null;
    };
    /** UserResponse */
    UserResponse: {
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Email */
      email: string;
      role: components["schemas"]["UserRole"];
      /** Is Active */
      is_active: boolean;
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /** Last Login At */
      last_login_at?: string | null;
    };
    /**
     * UserRole
     * @enum {string}
     */
    UserRole: "owner" | "editor" | "viewer";
    /** ValidationError */
    ValidationError: {
      /** Location */
      loc: (string | number)[];
      /** Message */
      msg: string;
      /** Error Type */
      type: string;
      /** Input */
      input?: unknown;
      /** Context */
      ctx?: Record<string, never>;
    };
    /**
     * WorkflowRule
     * @description Condição avaliada em código nosso, sem CEL; texto comparado sem maiúsculas.
     */
    WorkflowRule: {
      /**
       * Kind
       * @default always
       * @enum {string}
       */
      kind: "always" | "contains" | "not_contains" | "starts_with" | "empty" | "not_empty";
      /**
       * Source
       * @default previous
       * @enum {string}
       */
      source: "input" | "previous";
      /**
       * Value
       * @default
       */
      value: string;
    };
    /**
     * WorkflowSettings
     * @description Seção de workflow do payload. Só existe em config de kind=workflow.
     */
    WorkflowSettings: {
      /** Steps */
      steps: (
        | components["schemas"]["StepNode"]
        | components["schemas"]["ParallelNode"]
        | components["schemas"]["ConditionNode"]
        | components["schemas"]["LoopNode"]
      )[];
    };
  };
  responses: never;
  parameters: never;
  requestBodies: never;
  headers: never;
  pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
  list_pending_api_v1_approvals_get: {
    parameters: {
      query?: {
        agent_id?: string | null;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ApprovalItem"][];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  list_configs_api_v1_configs_get: {
    parameters: {
      query?: {
        page?: number;
        page_size?: number;
        /** @description Busca por nome (substring) ou ID exato */
        q?: string | null;
        status?: components["schemas"]["ConfigPayloadStatus"] | null;
        kind?: components["schemas"]["ConfigKind"] | null;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AgentConfigPage"];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  create_config_api_v1_configs_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["CreateConfigInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AgentConfigResponse"];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  get_config_api_v1_configs__config_id__get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        config_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AgentConfigDetail"];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  list_teams_using_api_v1_configs__config_id__teams_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        config_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AgentConfigResponse"][];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  list_versions_api_v1_configs__config_id__versions_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        config_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AgentConfigVersionDetail"][];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  publish_draft_api_v1_configs__config_id__publish_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        config_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AgentConfigVersionSummary"];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  rollback_api_v1_configs__config_id__rollback_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        config_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["RollbackInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AgentConfigVersionSummary"];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  save_draft_api_v1_configs__config_id__draft_put: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        config_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["DraftInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AgentConfigVersionSummary"];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  list_integrations_api_v1_integrations_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["IntegrationResponse"][];
        };
      };
    };
  };
  issue_api_v1_integrations_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["IntegrationInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["IssuedIntegration"];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  revoke_api_v1_integrations__integration_id__delete: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        integration_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["IntegrationResponse"];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  list_embedders_api_v1_knowledge_bases_embedders_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["EmbedderInfo"][];
        };
      };
    };
  };
  list_bases_api_v1_knowledge_bases_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["KnowledgeBaseResponse"][];
        };
      };
    };
  };
  create_base_api_v1_knowledge_bases_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["KnowledgeBaseCreate"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["KnowledgeBaseResponse"];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  get_base_api_v1_knowledge_bases__base_id__get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        base_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["KnowledgeBaseResponse"];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  update_base_api_v1_knowledge_bases__base_id__put: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        base_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["KnowledgeBaseUpdate"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["KnowledgeBaseResponse"];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  delete_base_api_v1_knowledge_bases__base_id__delete: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        base_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  search_api_v1_knowledge_bases__base_id__search_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        base_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["SearchInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["SearchHit"][];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  list_contents_api_v1_knowledge_bases__base_id__contents_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        base_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["KnowledgeContentResponse"][];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  get_content_api_v1_knowledge_bases__base_id__contents__content_id__get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        base_id: string;
        content_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["KnowledgeContentResponse"];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  delete_content_api_v1_knowledge_bases__base_id__contents__content_id__delete: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        base_id: string;
        content_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  upload_file_api_v1_knowledge_bases__base_id__contents_file_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        base_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "multipart/form-data": components["schemas"]["Body_upload_file_api_v1_knowledge_bases__base_id__contents_file_post"];
      };
    };
    responses: {
      /** @description Successful Response */
      202: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["KnowledgeContentResponse"];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  add_url_api_v1_knowledge_bases__base_id__contents_url_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        base_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["UrlContentInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      202: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["KnowledgeContentResponse"];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  add_text_api_v1_knowledge_bases__base_id__contents_text_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        base_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["TextContentInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      202: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["KnowledgeContentResponse"];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  list_capabilities_api_v1_models_capabilities_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": {
            [key: string]: {
              [key: string]: boolean;
            };
          };
        };
      };
    };
  };
  run_linter_api_v1_linter_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ConfigPayload"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["LintWarning"][];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  list_servers_api_v1_mcp_servers_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["McpServerResponse"][];
        };
      };
    };
  };
  create_server_api_v1_mcp_servers_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["McpServerInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["McpServerResponse"];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  get_server_api_v1_mcp_servers__server_id__get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        server_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["McpServerResponse"];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  update_server_api_v1_mcp_servers__server_id__put: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        server_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["McpServerInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["McpServerResponse"];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  delete_server_api_v1_mcp_servers__server_id__delete: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        server_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  discover_api_v1_mcp_servers__server_id__discover_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        server_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["McpServerResponse"];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  get_summary_api_v1_metrics_summary_get: {
    parameters: {
      query?: {
        period?: string;
        start?: string | null;
        end?: string | null;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["GlobalMetricsSummary"];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  get_by_agent_api_v1_metrics_by_agent_get: {
    parameters: {
      query?: {
        period?: string;
        start?: string | null;
        end?: string | null;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AgentBreakdownItem"][];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  get_timeseries_api_v1_metrics_timeseries_get: {
    parameters: {
      query?: {
        period?: string;
        start?: string | null;
        end?: string | null;
        agent_id?: string | null;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["DailyMetricsPoint"][];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  get_metrics_api_v1_configs__config_id__metrics_get: {
    parameters: {
      query?: {
        period?: string;
      };
      header?: never;
      path: {
        config_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AgentMetricsResponse"];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  list_runs_api_v1_configs__config_id__runs_get: {
    parameters: {
      query?: {
        page?: number;
        page_size?: number;
      };
      header?: never;
      path: {
        config_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["RunsPage"];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  get_run_trace_api_v1_runs__run_id__trace_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        run_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["RunTrace"];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  get_rollup_api_v1_usage_rollup_get: {
    parameters: {
      query?: {
        /** @description Período no formato YYYYMM. Vazio = mês corrente. */
        period?: string;
        agent_id?: string | null;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["RollupItem"][];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  list_users_api_v1_users_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["UserResponse"][];
        };
      };
    };
  };
  create_user_api_v1_users_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["CreateUserInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["UserResponse"];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  delete_user_api_v1_users__user_id__delete: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        user_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  update_user_api_v1_users__user_id__patch: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        user_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["UpdateUserInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["UserResponse"];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  reset_password_api_v1_users__user_id__password_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        user_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ResetPasswordInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["UserResponse"];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  me_api_v1_me_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MeResponse"];
        };
      };
    };
  };
  login_api_v1_auth_login_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["LoginInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["TokenResponse"];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  logout_api_v1_auth_logout_post: {
    parameters: {
      query?: never;
      header: {
        authorization: string;
      };
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  create_user_api_v1_auth_users_post: {
    parameters: {
      query?: never;
      header: {
        authorization: string;
      };
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["CreateUserInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["UserResponse"];
        };
      };
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
}
