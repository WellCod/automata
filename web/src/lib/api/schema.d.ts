export interface paths {
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
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** AgentConfigDetail */
        AgentConfigDetail: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
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
        };
        /** DraftInput */
        DraftInput: {
            /** Name */
            name: string;
            /** Description */
            description: string;
            payload: components["schemas"]["ConfigPayload"];
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
    list_configs_api_v1_configs_get: {
        parameters: {
            query?: {
                page?: number;
                page_size?: number;
                /** @description Busca por nome (substring) ou ID exato */
                q?: string | null;
                status?: components["schemas"]["ConfigPayloadStatus"] | null;
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
}
