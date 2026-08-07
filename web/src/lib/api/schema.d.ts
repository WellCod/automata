export interface paths {
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
}
export type webhooks = Record<string, never>;
export interface components {
  schemas: {
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
     * ConfigPayload
     * @description Payload JSONB de uma versão de configuração.
     *
     *     schema_version é guardado dentro do payload para permitir migrações
     *     de formato sem alterar a coluna — a lógica de upgrade fica no código,
     *     não no schema do banco.
     */
    ConfigPayload: {
      /**
       * Schema Version
       * @default 1
       * @constant
       */
      schema_version: 1;
      /** Model Id */
      model_id: string;
      instructions?: components["schemas"]["InstructionSections"];
      /** Tools */
      tools?: string[];
      capabilities?: components["schemas"]["CapabilityFlags"];
      /** Metadata */
      metadata?: {
        [key: string]: unknown;
      };
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
}
