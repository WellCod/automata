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
    /**
     * ConfigKind
     * @enum {string}
     */
    ConfigKind: "agent" | "team";
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
      model_id: string;
      instructions?: components["schemas"]["InstructionSections"];
      /** Mcp Servers */
      mcp_servers?: components["schemas"]["McpServerBinding"][];
      capabilities?: components["schemas"]["CapabilityFlags"];
      /** Metadata */
      metadata?: {
        [key: string]: unknown;
      };
      team?: components["schemas"]["TeamSettings"] | null;
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
    /** DraftInput */
    DraftInput: {
      /** Name */
      name: string;
      /** Description */
      description: string;
      payload: components["schemas"]["ConfigPayload"];
    };
    /** GlobalMetricsSummary */
    GlobalMetricsSummary: {
      /** Total Runs */
      total_runs: number;
      /** Error Rate */
      error_rate: number;
      /** P50 Ms */
      p50_ms: number | null;
      /** P95 Ms */
      p95_ms: number | null;
      /** Total Tokens */
      total_tokens: number;
      /** Total Cost */
      total_cost: number | null;
      /** Period Days */
      period_days: number;
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
