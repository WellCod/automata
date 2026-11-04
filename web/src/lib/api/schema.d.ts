export interface paths {
  "/api/v1/alert-destinations/channels": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Channels */
    get: operations["channels_api_v1_alert_destinations_channels_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/alert-destinations": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** List Destinations */
    get: operations["list_destinations_api_v1_alert_destinations_get"];
    put?: never;
    /**
     * Create Destination
     * @description Cadastra o destino; o segredo do webhook é devolvido uma vez só.
     */
    post: operations["create_destination_api_v1_alert_destinations_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/alert-destinations/{destination_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    /** Update Destination */
    put: operations["update_destination_api_v1_alert_destinations__destination_id__put"];
    post?: never;
    /** Delete Destination */
    delete: operations["delete_destination_api_v1_alert_destinations__destination_id__delete"];
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/alert-destinations/{destination_id}/test": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Test Destination
     * @description Manda um alert.test, uma tentativa só, para conferir a integração.
     */
    post: operations["test_destination_api_v1_alert_destinations__destination_id__test_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
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
  "/api/v1/configs/{config_id}/budget": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Read Budget */
    get: operations["read_budget_api_v1_configs__config_id__budget_get"];
    /** Update Budget */
    put: operations["update_budget_api_v1_configs__config_id__budget_put"];
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/caller-budgets": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** List Budgets */
    get: operations["list_budgets_api_v1_caller_budgets_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/caller-budgets/{subject}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    /** Put Budget */
    put: operations["put_budget_api_v1_caller_budgets__subject__put"];
    post?: never;
    /** Delete Budget */
    delete: operations["delete_budget_api_v1_caller_budgets__subject__delete"];
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
  "/api/v1/configs/{config_id}/guardrails/effective": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get Effective Guardrails */
    get: operations["get_effective_guardrails_api_v1_configs__config_id__guardrails_effective_get"];
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
  "/api/v1/data-subjects/{user_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get Subject */
    get: operations["get_subject_api_v1_data_subjects__user_id__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/data-subjects/{user_id}/export": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Export Subject */
    post: operations["export_subject_api_v1_data_subjects__user_id__export_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/data-subjects/{user_id}/erase": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Erase Subject */
    post: operations["erase_subject_api_v1_data_subjects__user_id__erase_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/data-subject-requests": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** List Requests */
    get: operations["list_requests_api_v1_data_subject_requests_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/data-subject-requests/{request_id}/download": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Download */
    get: operations["download_api_v1_data_subject_requests__request_id__download_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/me/data": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** My Inventory */
    get: operations["my_inventory_api_v1_me_data_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/me/data/export": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** My Export */
    post: operations["my_export_api_v1_me_data_export_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/me/data/erase": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** My Erase */
    post: operations["my_erase_api_v1_me_data_erase_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/me/data/requests": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** My Requests */
    get: operations["my_requests_api_v1_me_data_requests_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/me/data/requests/{request_id}/download": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** My Download */
    get: operations["my_download_api_v1_me_data_requests__request_id__download_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/instance-guardrails": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get Floor */
    get: operations["get_floor_api_v1_instance_guardrails_get"];
    /** Put Floor */
    put: operations["put_floor_api_v1_instance_guardrails_put"];
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/queue": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get Queue */
    get: operations["get_queue_api_v1_queue_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/queue/jobs/{job_id}/requeue": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Requeue Job */
    post: operations["requeue_job_api_v1_queue_jobs__job_id__requeue_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/configs/{config_id}/eval-cases": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** List Cases */
    get: operations["list_cases_api_v1_configs__config_id__eval_cases_get"];
    put?: never;
    /** Create Case */
    post: operations["create_case_api_v1_configs__config_id__eval_cases_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/configs/{config_id}/eval-cases/suggestion": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Suggest Case
     * @description Caso a partir de uma conversa real: o formulário abre preenchido e nada é gravado.
     */
    get: operations["suggest_case_api_v1_configs__config_id__eval_cases_suggestion_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/configs/{config_id}/eval-cases/{case_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    /** Update Case */
    put: operations["update_case_api_v1_configs__config_id__eval_cases__case_id__put"];
    post?: never;
    /** Delete Case */
    delete: operations["delete_case_api_v1_configs__config_id__eval_cases__case_id__delete"];
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/configs/{config_id}/eval-runs": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** List Runs */
    get: operations["list_runs_api_v1_configs__config_id__eval_runs_get"];
    put?: never;
    /** Start Run */
    post: operations["start_run_api_v1_configs__config_id__eval_runs_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/configs/{config_id}/eval-runs/compare": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Compare Runs
     * @description Caso a caso entre duas execuções; tipicamente a vigente (base) e o rascunho (target).
     */
    get: operations["compare_runs_api_v1_configs__config_id__eval_runs_compare_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/configs/{config_id}/eval-runs/{run_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get Run */
    get: operations["get_run_api_v1_configs__config_id__eval_runs__run_id__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/configs/{config_id}/eval-schedule": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Read Schedule
     * @description `null` quando a suíte não tem agendamento: é o estado normal, não um erro.
     */
    get: operations["read_schedule_api_v1_configs__config_id__eval_schedule_get"];
    /** Save Schedule */
    put: operations["save_schedule_api_v1_configs__config_id__eval_schedule_put"];
    post?: never;
    /** Delete Schedule */
    delete: operations["delete_schedule_api_v1_configs__config_id__eval_schedule_delete"];
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/configs/{config_id}/eval-schedule/webhook": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    /**
     * Save Webhook
     * @description Cadastra ou troca o webhook; o segredo novo é devolvido uma vez só.
     */
    put: operations["save_webhook_api_v1_configs__config_id__eval_schedule_webhook_put"];
    post?: never;
    /** Delete Webhook */
    delete: operations["delete_webhook_api_v1_configs__config_id__eval_schedule_webhook_delete"];
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/configs/{config_id}/eval-schedule/webhook/test": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Test Webhook
     * @description Manda um suite.test, uma tentativa só, para conferir a integração.
     */
    post: operations["test_webhook_api_v1_configs__config_id__eval_schedule_webhook_test_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/configs/{config_id}/eval-settings": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Read Eval Settings */
    get: operations["read_eval_settings_api_v1_configs__config_id__eval_settings_get"];
    /** Update Settings */
    put: operations["update_settings_api_v1_configs__config_id__eval_settings_put"];
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/eval-status": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List Suite Status
     * @description Estado da suíte de cada config que já rodou: para a lista de agentes e times.
     */
    get: operations["list_suite_status_api_v1_eval_status_get"];
    put?: never;
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
  "/api/v1/key-rotation": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Rotation Status */
    get: operations["rotation_status_api_v1_key_rotation_get"];
    put?: never;
    post?: never;
    delete?: never;
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
  "/api/v1/knowledge-bases/{base_id}/fields": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Field Values
     * @description Campos e valores dos documentos prontos da base: o que o modelo vê na tool.
     */
    get: operations["get_field_values_api_v1_knowledge_bases__base_id__fields_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/knowledge-bases/cross-encoders": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** List Cross Encoders */
    get: operations["list_cross_encoders_api_v1_knowledge_bases_cross_encoders_get"];
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
  "/api/v1/knowledge-bases/{base_id}/search/compare": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Compare Search
     * @description A mesma pergunta com a estratégia da base e com a busca simples, lado a lado.
     */
    post: operations["compare_search_api_v1_knowledge_bases__base_id__search_compare_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/knowledge-bases/{base_id}/chunk-preview": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Chunk Preview
     * @description Trechos que um texto ou conteúdo daria com o corte escolhido, sem embedding (ADR-0029).
     */
    post: operations["chunk_preview_api_v1_knowledge_bases__base_id__chunk_preview_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/knowledge-bases/{base_id}/reprocess": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Reprocess Base
     * @description Reindexa o conteúdo da base com o corte atual; o embedding é cobrado de novo.
     */
    post: operations["reprocess_base_api_v1_knowledge_bases__base_id__reprocess_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/knowledge-bases/{base_id}/connectors": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** List Connectors */
    get: operations["list_connectors_api_v1_knowledge_bases__base_id__connectors_get"];
    put?: never;
    /** Create Connector */
    post: operations["create_connector_api_v1_knowledge_bases__base_id__connectors_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/knowledge-bases/{base_id}/connectors/{connector_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    /** Update Connector */
    put: operations["update_connector_api_v1_knowledge_bases__base_id__connectors__connector_id__put"];
    post?: never;
    /**
     * Delete Connector
     * @description Os conteúdos do conector saem com ele, e os trechos antes.
     */
    delete: operations["delete_connector_api_v1_knowledge_bases__base_id__connectors__connector_id__delete"];
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/knowledge-bases/{base_id}/connectors/{connector_id}/test": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Test Connector
     * @description Lista a origem sem baixar nada: confere credencial, caminho e o que entraria.
     */
    post: operations["test_connector_api_v1_knowledge_bases__base_id__connectors__connector_id__test_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/knowledge-bases/{base_id}/connectors/{connector_id}/sync": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Sync Connector */
    post: operations["sync_connector_api_v1_knowledge_bases__base_id__connectors__connector_id__sync_post"];
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
  "/api/v1/knowledge-bases/{base_id}/contents/{content_id}/fields": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    /**
     * Update Fields
     * @description Campos do documento (ADR-0033): grava e atualiza os trechos já indexados, sem embedar.
     */
    put: operations["update_fields_api_v1_knowledge_bases__base_id__contents__content_id__fields_put"];
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/knowledge-bases/{base_id}/contents/{content_id}/schedule": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    /**
     * Update Schedule
     * @description Intervalo de reindexação de uma URL; vazio desliga.
     */
    put: operations["update_schedule_api_v1_knowledge_bases__base_id__contents__content_id__schedule_put"];
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/knowledge-bases/{base_id}/contents/{content_id}/refresh": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Refresh Content
     * @description Baixa a URL agora; só reindexa se o conteúdo mudou.
     */
    post: operations["refresh_content_api_v1_knowledge_bases__base_id__contents__content_id__refresh_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/models/prices": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List Prices
     * @description Dólar por milhão de tokens, com os ajustes de MODEL_PRICES (ADR-0021).
     */
    get: operations["list_prices_api_v1_models_prices_get"];
    put?: never;
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
  "/api/v1/configs/{config_id}/memories": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** List Agent Memories */
    get: operations["list_agent_memories_api_v1_configs__config_id__memories_get"];
    put?: never;
    post?: never;
    /**
     * Forget User
     * @description Pedido de exclusão: tudo o que este agente guardou sobre o usuário.
     */
    delete: operations["forget_user_api_v1_configs__config_id__memories_delete"];
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/configs/{config_id}/memories/{memory_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    /** Delete Agent Memory */
    delete: operations["delete_agent_memory_api_v1_configs__config_id__memories__memory_id__delete"];
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/me/memories": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** List My Memories */
    get: operations["list_my_memories_api_v1_me_memories_get"];
    put?: never;
    post?: never;
    /** Forget Me */
    delete: operations["forget_me_api_v1_me_memories_delete"];
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/v1/me/memories/{memory_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    /** Delete My Memory */
    delete: operations["delete_my_memory_api_v1_me_memories__memory_id__delete"];
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
  "/api/v1/metrics/reconciliation": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Reconciliation
     * @description Custo informado pelo provedor e estimado pelo Automata, por dia (ADR-0037).
     */
    get: operations["get_reconciliation_api_v1_metrics_reconciliation_get"];
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
  "/api/v1/runs/{run_id}/reviews": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Run Reviews
     * @description Decisões humanas do run do workflow (ADR-0028), na ordem em que aconteceram.
     *
     *     O antes e depois da edição é conteúdo da conversa: mesma regra do trace, só o
     *     dono do run ou o owner.
     */
    get: operations["get_run_reviews_api_v1_runs__run_id__reviews_get"];
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
      /**
       * Screened Tools
       * @default []
       */
      screened_tools: components["schemas"]["ScreenedTool"][];
      /** Stop Reason */
      stop_reason?: string | null;
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
    /** AlertChannels */
    AlertChannels: {
      /**
       * Webhook
       * @default true
       */
      webhook: boolean;
      /** Email */
      email: boolean;
    };
    /** AlertDestinationCreate */
    AlertDestinationCreate: {
      /** Name */
      name: string;
      /**
       * Kind
       * @default webhook
       * @enum {string}
       */
      kind: "webhook" | "email";
      /** Url */
      url?: string | null;
      /** Emails */
      emails?: string[];
      /** Events */
      events: (
        | "budget.warning"
        | "budget.exceeded"
        | "caller_budget.warning"
        | "caller_budget.exceeded"
        | "errors.spike"
        | "suite.regressed"
        | "suite.failing"
        | "suite.recovered"
        | "data_subject.failed"
        | "data_subject.due"
        | "job.failed"
        | "cost.divergence"
      )[];
    };
    /** AlertDestinationIssued */
    AlertDestinationIssued: {
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Name */
      name: string;
      /**
       * Kind
       * @default webhook
       */
      kind: string;
      /** Host */
      host: string;
      /**
       * Emails
       * @default []
       */
      emails: string[];
      /** Events */
      events: (
        | "budget.warning"
        | "budget.exceeded"
        | "caller_budget.warning"
        | "caller_budget.exceeded"
        | "errors.spike"
        | "suite.regressed"
        | "suite.failing"
        | "suite.recovered"
        | "data_subject.failed"
        | "data_subject.due"
        | "job.failed"
        | "cost.divergence"
      )[];
      /** Created By */
      created_by: string;
      /** Last Status */
      last_status: string | null;
      /** Last At */
      last_at: string | null;
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /** Secret */
      secret: string;
    };
    /** AlertDestinationResponse */
    AlertDestinationResponse: {
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Name */
      name: string;
      /**
       * Kind
       * @default webhook
       */
      kind: string;
      /** Host */
      host: string;
      /**
       * Emails
       * @default []
       */
      emails: string[];
      /** Events */
      events: (
        | "budget.warning"
        | "budget.exceeded"
        | "caller_budget.warning"
        | "caller_budget.exceeded"
        | "errors.spike"
        | "suite.regressed"
        | "suite.failing"
        | "suite.recovered"
        | "data_subject.failed"
        | "data_subject.due"
        | "job.failed"
        | "cost.divergence"
      )[];
      /** Created By */
      created_by: string;
      /** Last Status */
      last_status: string | null;
      /** Last At */
      last_at: string | null;
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
    };
    /** AlertDestinationUpdate */
    AlertDestinationUpdate: {
      /** Name */
      name: string;
      /** Events */
      events: (
        | "budget.warning"
        | "budget.exceeded"
        | "caller_budget.warning"
        | "caller_budget.exceeded"
        | "errors.spike"
        | "suite.regressed"
        | "suite.failing"
        | "suite.recovered"
        | "data_subject.failed"
        | "data_subject.due"
        | "job.failed"
        | "cost.divergence"
      )[];
    };
    /** AlertTestResult */
    AlertTestResult: {
      /** Status */
      status: string;
      /** Delivered */
      delivered: boolean;
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
      /** Kind */
      kind: string;
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
      /** Steps */
      steps: components["schemas"]["PendingStep"][];
    };
    /**
     * BlockedCheck
     * @description O run precisa ser barrado por guardrail; com `rule`, por essa regra (ADR-0022).
     */
    BlockedCheck: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      type: "blocked";
      /** Rule */
      rule?:
        | (
            | "pii_detected"
            | "prompt_injection"
            | "off_topic"
            | "input_too_long"
            | "moderation"
            | "classifier"
            | "output_not_allowed"
            | "output_classifier"
          )
        | null;
    };
    /** Body_upload_file_api_v1_knowledge_bases__base_id__contents_file_post */
    Body_upload_file_api_v1_knowledge_bases__base_id__contents_file_post: {
      /** File */
      file: string;
      /** Name */
      name?: string | null;
    };
    /** BudgetInput */
    BudgetInput: {
      /** Monthly Usd */
      monthly_usd?: number | null;
      /**
       * Alert Percent
       * @default 80
       */
      alert_percent: number;
      /**
       * Hard Stop
       * @default false
       */
      hard_stop: boolean;
    };
    /** BudgetResponse */
    BudgetResponse: {
      /** Monthly Usd */
      monthly_usd: number | null;
      /** Alert Percent */
      alert_percent: number;
      /** Hard Stop */
      hard_stop: boolean;
      /** Period */
      period: string;
      /** Spent Usd */
      spent_usd: number;
      /** Percent */
      percent: number | null;
      /** Level */
      level: ("ok" | "warning" | "exceeded") | null;
    };
    /** CallerBudgetInput */
    CallerBudgetInput: {
      /** Monthly Usd */
      monthly_usd: number;
      /**
       * Warn Percent
       * @default 80
       */
      warn_percent: number;
      /**
       * Hard Stop
       * @default false
       */
      hard_stop: boolean;
    };
    /** CallerBudgetResponse */
    CallerBudgetResponse: {
      /** Subject */
      subject: string;
      /** Label */
      label: string;
      /** Kind */
      kind: string;
      /** Monthly Usd */
      monthly_usd: number;
      /** Warn Percent */
      warn_percent: number;
      /** Hard Stop */
      hard_stop: boolean;
      /** Spent Usd */
      spent_usd: number;
      /** Percent */
      percent: number;
      /** Level */
      level: string;
      /**
       * Updated At
       * Format: date-time
       */
      updated_at: string;
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
    /** CaseComparison */
    CaseComparison: {
      /** Case Id */
      case_id: string | null;
      /** Case Name */
      case_name: string;
      /** Base Status */
      base_status: ("passed" | "failed" | "error" | "not_evaluated") | null;
      /** Target Status */
      target_status: ("passed" | "failed" | "error" | "not_evaluated") | null;
      /**
       * Change
       * @enum {string}
       */
      change: "regression" | "fix" | "same" | "new" | "removed";
    };
    /** ChunkPreview */
    ChunkPreview: {
      /** Chunks */
      chunks: string[];
      /** Total */
      total: number;
      /** Chunk Size */
      chunk_size: number;
      chunking: components["schemas"]["ChunkingSettings"];
    };
    /**
     * ChunkPreviewInput
     * @description Texto colado ou um conteúdo da base; a estratégia vazia é a gravada na base.
     */
    ChunkPreviewInput: {
      /** Text */
      text?: string | null;
      /** Content Id */
      content_id?: string | null;
      /** Chunk Size */
      chunk_size?: number | null;
      chunking?: components["schemas"]["ChunkingSettings"] | null;
    };
    /**
     * ChunkingSettings
     * @description Como o conteúdo da base é cortado em trechos (ADR-0029); vale para novas ingestões.
     */
    ChunkingSettings: {
      /**
       * Strategy
       * @default recursive
       * @enum {string}
       */
      strategy: "recursive" | "headings" | "paragraphs" | "fixed";
      /** Overlap */
      overlap?: number | null;
      /**
       * Heading Level
       * @default 2
       */
      heading_level: number;
    };
    /**
     * ClassifierRule
     * @description Classificador por modelo na entrada (ADR-0030): uma chamada por mensagem.
     */
    ClassifierRule: {
      /** Model Id */
      model_id: string;
      /** Checks */
      checks: ("injection" | "toxicity" | "off_topic")[];
      /**
       * Scope
       * @default
       */
      scope: string;
      /**
       * On Failure
       * @default allow
       * @enum {string}
       */
      on_failure: "allow" | "block";
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
      conversation?: components["schemas"]["ConversationSettings"];
      memory?: components["schemas"]["MemorySettings"];
      run?: components["schemas"]["RunControls"];
      /** Output Schema */
      output_schema?: {
        [key: string]: unknown;
      } | null;
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
    /** ConnectorInput */
    ConnectorInput: {
      /**
       * Kind
       * @enum {string}
       */
      kind: "github" | "s3" | "sharepoint";
      /** Name */
      name: string;
      /** Settings */
      settings: {
        [key: string]: unknown;
      };
      /** Secret */
      secret?: {
        [key: string]: string;
      } | null;
      /** Sync Every Hours */
      sync_every_hours?: number | null;
    };
    /** ConnectorResponse */
    ConnectorResponse: {
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
      /**
       * Kind
       * @enum {string}
       */
      kind: "github" | "s3" | "sharepoint";
      /** Name */
      name: string;
      /** Settings */
      settings: {
        [key: string]: unknown;
      };
      /** Has Secret */
      has_secret: boolean;
      /** Last Status */
      last_status: string;
      /** Last Message */
      last_message: string | null;
      /** Last Summary */
      last_summary: {
        [key: string]: unknown;
      } | null;
      /** Last Sync At */
      last_sync_at: string | null;
      /** Sync Every Hours */
      sync_every_hours: number | null;
      /** Next Sync At */
      next_sync_at: string | null;
      /** Content Count */
      content_count: number;
      /** Created By */
      created_by: string;
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
    };
    /** ConnectorTestResult */
    ConnectorTestResult: {
      /** Ok */
      ok: boolean;
      /** Files */
      files: number;
      /** Sample */
      sample: string[];
      /** Error */
      error: string | null;
    };
    /** ContentFieldsInput */
    ContentFieldsInput: {
      /** Fields */
      fields?: {
        [key: string]: string;
      } | null;
    };
    /** ContentScheduleInput */
    ContentScheduleInput: {
      /** Refresh Every Hours */
      refresh_every_hours?: number | null;
    };
    /**
     * ConversationSettings
     * @description Conversa longa (ADR-0019): turnos antigos viram resumo acima de um limite de tokens.
     */
    ConversationSettings: {
      /**
       * Compaction
       * @default false
       */
      compaction: boolean;
      /**
       * Compact At Tokens
       * @default 16000
       */
      compact_at_tokens: number;
      /**
       * Keep Recent Runs
       * @default 3
       */
      keep_recent_runs: number;
      /** Summary Instructions */
      summary_instructions?: string | null;
      /**
       * Search History
       * @default true
       */
      search_history: boolean;
      /** Summary Model */
      summary_model?: string | null;
    };
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
    /** CrossEncoderInfo */
    CrossEncoderInfo: {
      /**
       * Provider
       * @enum {string}
       */
      provider: "cohere" | "bedrock";
      /** Models */
      models: string[];
      /** Configured */
      configured: boolean;
      /** Price Per Search */
      price_per_search: {
        [key: string]: number;
      };
    };
    /**
     * CrossEncoderSettings
     * @description Reranker que lê a pergunta e o trecho juntos (ADR-0033); o texto sai para o provedor.
     */
    CrossEncoderSettings: {
      /**
       * Provider
       * @enum {string}
       */
      provider: "cohere" | "bedrock";
      /**
       * Model
       * @default
       */
      model: string;
    };
    /**
     * CustomPiiPattern
     * @description Dado pessoal da empresa (matrícula, contrato, protocolo) pelo formato (ADR-0032).
     *
     *     Sem regex livre: prefixo literal e a faixa de dígitos, montados em regex pelo código.
     */
    CustomPiiPattern: {
      /** Label */
      label: string;
      /**
       * Prefix
       * @default
       */
      prefix: string;
      /** Min Digits */
      min_digits: number;
      /** Max Digits */
      max_digits: number;
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
    /** DataSubjectRequestResponse */
    DataSubjectRequestResponse: {
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Kind */
      kind: string;
      /** Subject */
      subject: string | null;
      /** Subject Hash */
      subject_hash: string;
      /** Status */
      status: string;
      /** Requested By */
      requested_by: string;
      /** Source */
      source: string;
      /** Due At */
      due_at?: string | null;
      /** Counts */
      counts: {
        [key: string]: unknown;
      } | null;
      /** Error */
      error: string | null;
      /** Expires At */
      expires_at: string | null;
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /** Finished At */
      finished_at: string | null;
    };
    /** DraftInput */
    DraftInput: {
      /** Name */
      name: string;
      /** Description */
      description: string;
      payload: components["schemas"]["ConfigPayload"];
    };
    /**
     * EffectiveGuardrails
     * @description Guardrails da versão, o piso da instância e o que vale no run (ADR-0034).
     */
    EffectiveGuardrails: {
      own: components["schemas"]["GuardrailSettings"];
      floor: components["schemas"]["GuardrailSettings"] | null;
      effective: components["schemas"]["GuardrailSettings"];
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
    /** EraseInput */
    EraseInput: {
      /** Confirm */
      confirm: string;
    };
    /** EvalCaseInput */
    EvalCaseInput: {
      /** Name */
      name: string;
      /** Input */
      input: string;
      /** Context */
      context?: string[];
      /** Checks */
      checks: (
        | components["schemas"]["TextCheck"]
        | components["schemas"]["ToolsCheck"]
        | components["schemas"]["JudgeCheck"]
        | components["schemas"]["BlockedCheck"]
        | components["schemas"]["StepsCheck"]
        | components["schemas"]["SchemaCheck"]
      )[];
      /** Source Run Id */
      source_run_id?: string | null;
    };
    /** EvalCaseResponse */
    EvalCaseResponse: {
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
      /** Name */
      name: string;
      /** Input */
      input: string;
      /** Context */
      context: string[];
      /** Checks */
      checks: (
        | components["schemas"]["TextCheck"]
        | components["schemas"]["ToolsCheck"]
        | components["schemas"]["JudgeCheck"]
        | components["schemas"]["BlockedCheck"]
        | components["schemas"]["StepsCheck"]
        | components["schemas"]["SchemaCheck"]
      )[];
      /** Source Run Id */
      source_run_id: string | null;
      /** Position */
      position: number;
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
    /**
     * EvalCaseSuggestion
     * @description Caso montado de um run real; nada é gravado até o editor salvar pelo POST de casos.
     */
    EvalCaseSuggestion: {
      /** Name */
      name: string;
      /** Input */
      input: string;
      /** Context */
      context: string[];
      /** Checks */
      checks: (
        | components["schemas"]["TextCheck"]
        | components["schemas"]["ToolsCheck"]
        | components["schemas"]["JudgeCheck"]
        | components["schemas"]["BlockedCheck"]
        | components["schemas"]["StepsCheck"]
        | components["schemas"]["SchemaCheck"]
      )[];
      /** Judge Criteria */
      judge_criteria: string | null;
      /** Source Run Id */
      source_run_id: string;
      /** Notes */
      notes: string[];
    };
    /** EvalComparison */
    EvalComparison: {
      base: components["schemas"]["EvalRunSummary"];
      target: components["schemas"]["EvalRunSummary"];
      /** Cases */
      cases: components["schemas"]["CaseComparison"][];
      /** Regressions */
      regressions: number;
      /** Fixes */
      fixes: number;
    };
    /** EvalResultResponse */
    EvalResultResponse: {
      /**
       * Id
       * Format: uuid
       */
      id: string;
      /** Case Id */
      case_id: string | null;
      /** Case Name */
      case_name: string;
      /** Position */
      position: number;
      /**
       * Status
       * @enum {string}
       */
      status: "passed" | "failed" | "error" | "not_evaluated";
      /** Checks */
      checks: {
        [key: string]: unknown;
      }[];
      /** Output */
      output: string | null;
      /** Tools Called */
      tools_called: string[];
      /** Duration Ms */
      duration_ms: number | null;
      /** Error */
      error: string | null;
      /** Session Id */
      session_id: string | null;
    };
    /** EvalRunCreate */
    EvalRunCreate: {
      /** Version Id */
      version_id?: string | null;
      /** Target */
      target?: ("draft" | "current") | null;
      /** Judge Model */
      judge_model?: string | null;
    };
    /** EvalRunDetail */
    EvalRunDetail: {
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
      /**
       * Version Id
       * Format: uuid
       */
      version_id: string;
      /** Version Number */
      version_number: number;
      /** Version Status */
      version_status: string;
      /**
       * Status
       * @enum {string}
       */
      status: "queued" | "running" | "completed" | "failed";
      /** Total */
      total: number;
      /** Passed */
      passed: number;
      /** Failed */
      failed: number;
      /** Not Evaluated */
      not_evaluated: number;
      /** Error */
      error: string | null;
      /** Judge Model */
      judge_model: string | null;
      /** Total Tokens */
      total_tokens: number;
      /** Cost */
      cost: number | null;
      /** Started By */
      started_by: string;
      /**
       * Trigger
       * @enum {string}
       */
      trigger: "manual" | "integration" | "schedule";
      /** Target */
      target: ("draft" | "current") | null;
      /**
       * Verdict
       * @enum {string}
       */
      verdict: "pending" | "passed" | "failed";
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /** Started At */
      started_at: string | null;
      /** Finished At */
      finished_at: string | null;
      /** Results */
      results: components["schemas"]["EvalResultResponse"][];
    };
    /** EvalRunSummary */
    EvalRunSummary: {
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
      /**
       * Version Id
       * Format: uuid
       */
      version_id: string;
      /** Version Number */
      version_number: number;
      /** Version Status */
      version_status: string;
      /**
       * Status
       * @enum {string}
       */
      status: "queued" | "running" | "completed" | "failed";
      /** Total */
      total: number;
      /** Passed */
      passed: number;
      /** Failed */
      failed: number;
      /** Not Evaluated */
      not_evaluated: number;
      /** Error */
      error: string | null;
      /** Judge Model */
      judge_model: string | null;
      /** Total Tokens */
      total_tokens: number;
      /** Cost */
      cost: number | null;
      /** Started By */
      started_by: string;
      /**
       * Trigger
       * @enum {string}
       */
      trigger: "manual" | "integration" | "schedule";
      /** Target */
      target: ("draft" | "current") | null;
      /**
       * Verdict
       * @enum {string}
       */
      verdict: "pending" | "passed" | "failed";
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /** Started At */
      started_at: string | null;
      /** Finished At */
      finished_at: string | null;
    };
    /** EvalScheduleInput */
    EvalScheduleInput: {
      /** Cron Expr */
      cron_expr: string;
      /**
       * Timezone
       * @default America/Sao_Paulo
       */
      timezone: string;
      /**
       * Target
       * @default current
       * @enum {string}
       */
      target: "draft" | "current";
      /** Judge Model */
      judge_model?: string | null;
      /**
       * Enabled
       * @default true
       */
      enabled: boolean;
    };
    /** EvalScheduleResponse */
    EvalScheduleResponse: {
      /**
       * Agent Config Id
       * Format: uuid
       */
      agent_config_id: string;
      /** Cron Expr */
      cron_expr: string;
      /** Timezone */
      timezone: string;
      /**
       * Target
       * @enum {string}
       */
      target: "draft" | "current";
      /** Judge Model */
      judge_model: string | null;
      /** Enabled */
      enabled: boolean;
      /** Next Run At */
      next_run_at: string | null;
      /** Last Attempt At */
      last_attempt_at: string | null;
      /** Last Run Id */
      last_run_id: string | null;
      /** Last Error */
      last_error: string | null;
      /** Webhook Host */
      webhook_host: string | null;
      /** Webhook Last Status */
      webhook_last_status: string | null;
      /** Webhook Last At */
      webhook_last_at: string | null;
      /** Updated By */
      updated_by: string;
      /**
       * Updated At
       * Format: date-time
       */
      updated_at: string;
    };
    /** EvalSettings */
    EvalSettings: {
      /** Require Passing Evals */
      require_passing_evals: boolean;
      /** Draft Version Id */
      draft_version_id: string | null;
      draft_run: components["schemas"]["EvalRunSummary"] | null;
      /** Can Publish */
      can_publish: boolean;
      /** Reason */
      reason: string | null;
    };
    /** EvalSettingsInput */
    EvalSettingsInput: {
      /** Require Passing Evals */
      require_passing_evals: boolean;
    };
    /** EvalSuiteStatus */
    EvalSuiteStatus: {
      /**
       * Config Id
       * Format: uuid
       */
      config_id: string;
      /**
       * State
       * @enum {string}
       */
      state: "running" | "passing" | "failing" | "regressed";
      last_run: components["schemas"]["EvalRunSummary"];
      /** Previous Run Id */
      previous_run_id: string | null;
      /** Regressions */
      regressions: number;
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
      /**
       * Eval Tokens
       * @default 0
       */
      eval_tokens: number;
      /** Eval Cost */
      eval_cost?: number | null;
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
      classifier?: components["schemas"]["ClassifierRule"] | null;
      tool_results?: components["schemas"]["ToolResultScreening"] | null;
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
    /** InstanceGuardrailsInput */
    InstanceGuardrailsInput: {
      settings: components["schemas"]["GuardrailSettings"] | null;
    };
    /** InstanceGuardrailsResponse */
    InstanceGuardrailsResponse: {
      settings: components["schemas"]["GuardrailSettings"] | null;
      /** Updated By */
      updated_by?: string | null;
      /** Updated At */
      updated_at?: string | null;
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
      /** Eval Ids */
      eval_ids?: string[];
      /**
       * Data Subjects
       * @default false
       */
      data_subjects: boolean;
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
      /** Eval Ids */
      eval_ids: string[];
      /**
       * Data Subjects
       * @default false
       */
      data_subjects: boolean;
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
      /** On Current Key */
      on_current_key: boolean;
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
      /** Eval Ids */
      eval_ids: string[];
      /**
       * Data Subjects
       * @default false
       */
      data_subjects: boolean;
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
      /** On Current Key */
      on_current_key: boolean;
      /** Token */
      token: string;
      /** Mcp Url */
      mcp_url: string | null;
    };
    /**
     * JudgeCheck
     * @description Critério avaliado por um modelo juiz (AgentAsJudgeEval do Agno).
     */
    JudgeCheck: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      type: "judge";
      /** Criteria */
      criteria: string;
      /**
       * Mode
       * @default binary
       * @enum {string}
       */
      mode: "binary" | "numeric";
      /**
       * Threshold
       * @default 7
       */
      threshold: number;
    };
    /** JwtRotation */
    JwtRotation: {
      /** Current Kid */
      current_kid: string | null;
      /** Previous Kid */
      previous_kid: string | null;
      /** Tokens On Previous */
      tokens_on_previous: number;
      /** Tokens Without Kid */
      tokens_without_kid: number;
    };
    /** KeyRotationStatus */
    KeyRotationStatus: {
      jwt: components["schemas"]["JwtRotation"];
      secrets: components["schemas"]["SecretsRotation"];
      /** Done */
      done: boolean;
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
      retrieval?: components["schemas"]["RetrievalSettings"] | null;
      chunking?: components["schemas"]["ChunkingSettings"] | null;
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
      retrieval: components["schemas"]["RetrievalSettings"];
      chunking: components["schemas"]["ChunkingSettings"];
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
      retrieval?: components["schemas"]["RetrievalSettings"] | null;
      chunking?: components["schemas"]["ChunkingSettings"] | null;
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
      source_type: "file" | "url" | "text" | "connector";
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
      /**
       * Suspect Chunks
       * @default 0
       */
      suspect_chunks: number;
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
      /** Connector Id */
      connector_id?: string | null;
      /** External Path */
      external_path?: string | null;
      /** Refresh Every Hours */
      refresh_every_hours?: number | null;
      /** Next Refresh At */
      next_refresh_at?: string | null;
      /** Fields */
      fields?: {
        [key: string]: string;
      } | null;
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
      review?: components["schemas"]["LoopReview"] | null;
    };
    /**
     * LoopReview
     * @description Pausa ao fim de cada volta, menos a última (ADR-0028).
     *
     *     Aprovar encerra o laço e segue o workflow; recusar pede outra volta com o comentário.
     */
    LoopReview: {
      /**
       * Message
       * @default
       */
      message: string;
      /** Timeout Hours */
      timeout_hours?: number | null;
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
    /** MeEraseInput */
    MeEraseInput: {
      /** Confirm */
      confirm: string;
    };
    /** MeResponse */
    MeResponse: {
      /** Id */
      id: string;
      /** Email */
      email: string | null;
      role: components["schemas"]["UserRole"] | null;
    };
    /** MemoryItem */
    MemoryItem: {
      /** Memory Id */
      memory_id: string;
      /** User Id */
      user_id: string | null;
      /** Agent Id */
      agent_id: string | null;
      /** Agent Name */
      agent_name?: string | null;
      /** Memory */
      memory: string;
      /** Topics */
      topics: string[];
      /** Updated At */
      updated_at: string | null;
    };
    /**
     * MemorySettings
     * @description Memória do usuário entre sessões (ADR-0025): só deste agente, mascarada e com prazo.
     */
    MemorySettings: {
      /**
       * Enabled
       * @default false
       */
      enabled: boolean;
      /** Instructions */
      instructions?: string | null;
      /**
       * Retention Days
       * @default 90
       */
      retention_days: number;
    };
    /**
     * OutputClassifierRule
     * @description Classificador por modelo na resposta (ADR-0034): uma chamada por resposta.
     */
    OutputClassifierRule: {
      /** Model Id */
      model_id: string;
      /** Checks */
      checks: ("toxicity" | "off_topic" | "prompt_leak")[];
      /**
       * Scope
       * @default
       */
      scope: string;
      /**
       * On Failure
       * @default allow
       * @enum {string}
       */
      on_failure: "allow" | "block";
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
      classifier?: components["schemas"]["OutputClassifierRule"] | null;
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
    /** PendingStep */
    PendingStep: {
      /** Step Id */
      step_id: string | null;
      /** Step Name */
      step_name: string | null;
      /**
       * When
       * @enum {string}
       */
      when: "before" | "after" | "loop";
      /** Message */
      message: string | null;
      /** Output */
      output: string | null;
      /** Timeout At */
      timeout_at: string | null;
      /**
       * Retry Count
       * @default 0
       */
      retry_count: number;
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
      /** Custom */
      custom?: components["schemas"]["CustomPiiPattern"][];
    };
    /** QueueJob */
    QueueJob: {
      /** Id */
      id: string;
      /** Component Type */
      component_type: string | null;
      /** Component Id */
      component_id: string | null;
      /** Component Name */
      component_name: string | null;
      /** Status */
      status: string | null;
      /** Attempt */
      attempt: number;
      /** Max Attempts */
      max_attempts: number;
      /** Error */
      error: string | null;
      /** User Id */
      user_id: string | null;
      /** Created At */
      created_at: string | null;
      /** Completed At */
      completed_at: string | null;
    };
    /** QueueSummary */
    QueueSummary: {
      /** Durable */
      durable: boolean;
      /** Counts */
      counts: {
        [key: string]: number;
      };
      /** Oldest Queued At */
      oldest_queued_at: string | null;
      /** Jobs */
      jobs: components["schemas"]["QueueJob"][];
    };
    /** Reconciliation */
    Reconciliation: {
      /** Providers */
      providers: string[];
      /** Alert Percent */
      alert_percent: number;
      /** Rows */
      rows: components["schemas"]["ReconciliationRow"][];
    };
    /** ReconciliationRow */
    ReconciliationRow: {
      /** Provider */
      provider: string;
      /**
       * Day
       * Format: date
       */
      day: string;
      /** Reported Usd */
      reported_usd: number;
      /** Estimated Usd */
      estimated_usd: number;
      /** Diff Usd */
      diff_usd: number;
      /** Diff Percent */
      diff_percent: number | null;
      /** Closed */
      closed: boolean;
      /**
       * Fetched At
       * Format: date-time
       */
      fetched_at: string;
    };
    /** ReprocessResult */
    ReprocessResult: {
      /** Queued */
      queued: number;
      /** Needs Upload */
      needs_upload: components["schemas"]["KnowledgeContentResponse"][];
      /** Skipped */
      skipped: number;
    };
    /** ResetPasswordInput */
    ResetPasswordInput: {
      /** Password */
      password: string;
    };
    /**
     * RetrievalSettings
     * @description Estratégia de busca da base (ADR-0017): vale para todos os agentes que a usam.
     */
    RetrievalSettings: {
      /**
       * Reranker
       * @default none
       * @enum {string}
       */
      reranker: "none" | "mmr" | "recency";
      /**
       * Mmr Lambda
       * @default 0.5
       */
      mmr_lambda: number;
      /**
       * Recency Half Life Days
       * @default 30
       */
      recency_half_life_days: number;
      /**
       * Recency Weight
       * @default 0.3
       */
      recency_weight: number;
      /**
       * Hyde
       * @default false
       */
      hyde: boolean;
      /** Hyde Model */
      hyde_model?: string | null;
      cross_encoder?: components["schemas"]["CrossEncoderSettings"] | null;
      /**
       * Agentic Filters
       * @default false
       */
      agentic_filters: boolean;
    };
    /** ReviewEntry */
    ReviewEntry: {
      /** Step Id */
      step_id: string;
      /** Step Name */
      step_name?: string | null;
      /** Decision */
      decision: string;
      /** By */
      by: string;
      /**
       * At
       * Format: date-time
       */
      at: string;
      /** Feedback */
      feedback?: string | null;
      /** Before */
      before?: string | null;
      /** After */
      after?: string | null;
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
    /**
     * RunControls
     * @description Controle do run (ADR-0027). Padrão vazio: nenhum agente publicado muda sem versão nova.
     */
    RunControls: {
      /** Tool Call Limit */
      tool_call_limit?: number | null;
      /**
       * Provider Retries
       * @default 0
       */
      provider_retries: number;
      /** Fallback Models */
      fallback_models?: string[];
      compress_tool_results?: components["schemas"]["ToolCompression"] | null;
      /** Max Cost Usd */
      max_cost_usd?: number | null;
      /**
       * Background Retries
       * @default 0
       */
      background_retries: number;
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
    /**
     * SchemaCheck
     * @description A resposta valida contra o JSON Schema da versão testada (ADR-0027).
     */
    SchemaCheck: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      type: "schema";
    };
    /**
     * ScreenedTool
     * @description Resultado de tool retirado (ADR-0030); o trecho fica só no banco.
     */
    ScreenedTool: {
      /** Tool */
      tool: string;
      /** Rule */
      rule: string;
      /** Term */
      term?: string | null;
    };
    /** SearchComparison */
    SearchComparison: {
      with_strategy: components["schemas"]["SearchResult"];
      without_strategy: components["schemas"]["SearchResult"];
      retrieval: components["schemas"]["RetrievalSettings"];
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
      /** Filters */
      filters?: {
        [key: string]: string;
      } | null;
    };
    /** SearchResult */
    SearchResult: {
      /** Hits */
      hits: components["schemas"]["SearchHit"][];
      /** Searched */
      searched: string;
      /** Hyde Tokens */
      hyde_tokens: number;
      /** Rerank Cost */
      rerank_cost?: number | null;
      /**
       * Filters Dropped
       * @default false
       */
      filters_dropped: boolean;
    };
    /** SecretsRotation */
    SecretsRotation: {
      /** Configured */
      configured: boolean;
      /** Previous Configured */
      previous_configured: boolean;
      /** Pending */
      pending: {
        [key: string]: number;
      };
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
      review?: components["schemas"]["StepReview"] | null;
    };
    /**
     * StepReview
     * @description Pausa humana na etapa (ADR-0023): confirma antes de rodar ou aprova a saída.
     */
    StepReview: {
      /**
       * When
       * @enum {string}
       */
      when: "before" | "after";
      /**
       * Message
       * @default
       */
      message: string;
      /**
       * On Reject
       * @default cancel
       * @enum {string}
       */
      on_reject: "skip" | "cancel" | "retry";
      /** Timeout Hours */
      timeout_hours?: number | null;
    };
    /**
     * StepsCheck
     * @description Etapas do workflow que precisam ter rodado (ADR-0022).
     */
    StepsCheck: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      type: "steps";
      /** Steps */
      steps: string[];
      /**
       * Exclusive
       * @default false
       */
      exclusive: boolean;
    };
    /** SubjectInventory */
    SubjectInventory: {
      /** User Id */
      user_id: string;
      /** Counts */
      counts: {
        [key: string]: number;
      };
      /** Total */
      total: number;
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
    /**
     * TextCheck
     * @description Regra sobre a resposta, a mesma dos workflows; "sempre" não entra, passaria sem checar.
     */
    TextCheck: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      type: "text";
      /**
       * Kind
       * @enum {string}
       */
      kind: "contains" | "not_contains" | "starts_with" | "empty" | "not_empty";
      /**
       * Value
       * @default
       */
      value: string;
    };
    /** TextContentInput */
    TextContentInput: {
      /** Name */
      name: string;
      /** Text */
      text: string;
      /** Fields */
      fields?: {
        [key: string]: string;
      } | null;
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
    /**
     * ToolCompression
     * @description Resultado de tool resumido por um modelo antes de seguir no contexto (ADR-0029).
     */
    ToolCompression: {
      /**
       * After Results
       * @default 3
       */
      after_results: number;
      /** Token Limit */
      token_limit?: number | null;
      /** Model Id */
      model_id?: string | null;
    };
    /**
     * ToolResultScreening
     * @description Resultado de tool examinado antes de voltar ao modelo (ADR-0030).
     */
    ToolResultScreening: {
      /**
       * Terms
       * @default true
       */
      terms: boolean;
      /**
       * Classifier
       * @default false
       */
      classifier: boolean;
    };
    /**
     * ToolsCheck
     * @description Tools que o run precisa chamar (ReliabilityEval do Agno).
     */
    ToolsCheck: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      type: "tools";
      /** Tools */
      tools: string[];
      /**
       * Allow Additional
       * @default true
       */
      allow_additional: boolean;
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
      /** Refresh Every Hours */
      refresh_every_hours?: number | null;
      /** Fields */
      fields?: {
        [key: string]: string;
      } | null;
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
    /** WebhookInput */
    WebhookInput: {
      /** Url */
      url: string;
    };
    /** WebhookIssued */
    WebhookIssued: {
      /** Host */
      host: string;
      /** Secret */
      secret: string;
    };
    /** WebhookTestResult */
    WebhookTestResult: {
      /** Status */
      status: string;
      /** Delivered */
      delivered: boolean;
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
  channels_api_v1_alert_destinations_channels_get: {
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
          "application/json": components["schemas"]["AlertChannels"];
        };
      };
    };
  };
  list_destinations_api_v1_alert_destinations_get: {
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
          "application/json": components["schemas"]["AlertDestinationResponse"][];
        };
      };
    };
  };
  create_destination_api_v1_alert_destinations_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["AlertDestinationCreate"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AlertDestinationIssued"];
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
  update_destination_api_v1_alert_destinations__destination_id__put: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        destination_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["AlertDestinationUpdate"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AlertDestinationResponse"];
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
  delete_destination_api_v1_alert_destinations__destination_id__delete: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        destination_id: string;
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
  test_destination_api_v1_alert_destinations__destination_id__test_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        destination_id: string;
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
          "application/json": components["schemas"]["AlertTestResult"];
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
  read_budget_api_v1_configs__config_id__budget_get: {
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
          "application/json": components["schemas"]["BudgetResponse"];
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
  update_budget_api_v1_configs__config_id__budget_put: {
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
        "application/json": components["schemas"]["BudgetInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["BudgetResponse"];
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
  list_budgets_api_v1_caller_budgets_get: {
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
          "application/json": components["schemas"]["CallerBudgetResponse"][];
        };
      };
    };
  };
  put_budget_api_v1_caller_budgets__subject__put: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        subject: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["CallerBudgetInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["CallerBudgetResponse"];
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
  delete_budget_api_v1_caller_budgets__subject__delete: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        subject: string;
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
  get_effective_guardrails_api_v1_configs__config_id__guardrails_effective_get: {
    parameters: {
      query?: {
        draft?: boolean;
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
          "application/json": components["schemas"]["EffectiveGuardrails"];
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
  get_subject_api_v1_data_subjects__user_id__get: {
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
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["SubjectInventory"];
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
  export_subject_api_v1_data_subjects__user_id__export_post: {
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
      202: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["DataSubjectRequestResponse"];
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
  erase_subject_api_v1_data_subjects__user_id__erase_post: {
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
        "application/json": components["schemas"]["EraseInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      202: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["DataSubjectRequestResponse"];
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
  list_requests_api_v1_data_subject_requests_get: {
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
          "application/json": components["schemas"]["DataSubjectRequestResponse"][];
        };
      };
    };
  };
  download_api_v1_data_subject_requests__request_id__download_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        request_id: string;
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
          "application/json": unknown;
          "application/gzip": unknown;
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
  my_inventory_api_v1_me_data_get: {
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
          "application/json": components["schemas"]["SubjectInventory"];
        };
      };
    };
  };
  my_export_api_v1_me_data_export_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      202: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["DataSubjectRequestResponse"];
        };
      };
    };
  };
  my_erase_api_v1_me_data_erase_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["MeEraseInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      202: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["DataSubjectRequestResponse"];
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
  my_requests_api_v1_me_data_requests_get: {
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
          "application/json": components["schemas"]["DataSubjectRequestResponse"][];
        };
      };
    };
  };
  my_download_api_v1_me_data_requests__request_id__download_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        request_id: string;
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
          "application/json": unknown;
          "application/gzip": unknown;
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
  get_floor_api_v1_instance_guardrails_get: {
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
          "application/json": components["schemas"]["InstanceGuardrailsResponse"];
        };
      };
    };
  };
  put_floor_api_v1_instance_guardrails_put: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["InstanceGuardrailsInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["InstanceGuardrailsResponse"];
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
  get_queue_api_v1_queue_get: {
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
          "application/json": components["schemas"]["QueueSummary"];
        };
      };
    };
  };
  requeue_job_api_v1_queue_jobs__job_id__requeue_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        job_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      202: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": {
            [key: string]: string;
          };
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
  list_cases_api_v1_configs__config_id__eval_cases_get: {
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
          "application/json": components["schemas"]["EvalCaseResponse"][];
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
  create_case_api_v1_configs__config_id__eval_cases_post: {
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
        "application/json": components["schemas"]["EvalCaseInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["EvalCaseResponse"];
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
  suggest_case_api_v1_configs__config_id__eval_cases_suggestion_get: {
    parameters: {
      query: {
        run_id: string;
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
          "application/json": components["schemas"]["EvalCaseSuggestion"];
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
  update_case_api_v1_configs__config_id__eval_cases__case_id__put: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        config_id: string;
        case_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["EvalCaseInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["EvalCaseResponse"];
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
  delete_case_api_v1_configs__config_id__eval_cases__case_id__delete: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        config_id: string;
        case_id: string;
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
  list_runs_api_v1_configs__config_id__eval_runs_get: {
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
          "application/json": components["schemas"]["EvalRunSummary"][];
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
  start_run_api_v1_configs__config_id__eval_runs_post: {
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
        "application/json": components["schemas"]["EvalRunCreate"];
      };
    };
    responses: {
      /** @description Successful Response */
      202: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["EvalRunSummary"];
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
  compare_runs_api_v1_configs__config_id__eval_runs_compare_get: {
    parameters: {
      query: {
        base: string;
        target: string;
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
          "application/json": components["schemas"]["EvalComparison"];
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
  get_run_api_v1_configs__config_id__eval_runs__run_id__get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        config_id: string;
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
          "application/json": components["schemas"]["EvalRunDetail"];
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
  read_schedule_api_v1_configs__config_id__eval_schedule_get: {
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
          "application/json": components["schemas"]["EvalScheduleResponse"] | null;
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
  save_schedule_api_v1_configs__config_id__eval_schedule_put: {
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
        "application/json": components["schemas"]["EvalScheduleInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["EvalScheduleResponse"];
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
  delete_schedule_api_v1_configs__config_id__eval_schedule_delete: {
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
  save_webhook_api_v1_configs__config_id__eval_schedule_webhook_put: {
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
        "application/json": components["schemas"]["WebhookInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["WebhookIssued"];
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
  delete_webhook_api_v1_configs__config_id__eval_schedule_webhook_delete: {
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
  test_webhook_api_v1_configs__config_id__eval_schedule_webhook_test_post: {
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
          "application/json": components["schemas"]["WebhookTestResult"];
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
  read_eval_settings_api_v1_configs__config_id__eval_settings_get: {
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
          "application/json": components["schemas"]["EvalSettings"];
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
  update_settings_api_v1_configs__config_id__eval_settings_put: {
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
        "application/json": components["schemas"]["EvalSettingsInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["EvalSettings"];
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
  list_suite_status_api_v1_eval_status_get: {
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
          "application/json": components["schemas"]["EvalSuiteStatus"][];
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
  rotation_status_api_v1_key_rotation_get: {
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
          "application/json": components["schemas"]["KeyRotationStatus"];
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
  get_field_values_api_v1_knowledge_bases__base_id__fields_get: {
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
          "application/json": {
            [key: string]: string[];
          };
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
  list_cross_encoders_api_v1_knowledge_bases_cross_encoders_get: {
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
          "application/json": components["schemas"]["CrossEncoderInfo"][];
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
  compare_search_api_v1_knowledge_bases__base_id__search_compare_post: {
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
          "application/json": components["schemas"]["SearchComparison"];
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
  chunk_preview_api_v1_knowledge_bases__base_id__chunk_preview_post: {
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
        "application/json": components["schemas"]["ChunkPreviewInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ChunkPreview"];
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
  reprocess_base_api_v1_knowledge_bases__base_id__reprocess_post: {
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
      202: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ReprocessResult"];
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
  list_connectors_api_v1_knowledge_bases__base_id__connectors_get: {
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
          "application/json": components["schemas"]["ConnectorResponse"][];
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
  create_connector_api_v1_knowledge_bases__base_id__connectors_post: {
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
        "application/json": components["schemas"]["ConnectorInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ConnectorResponse"];
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
  update_connector_api_v1_knowledge_bases__base_id__connectors__connector_id__put: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        base_id: string;
        connector_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ConnectorInput"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ConnectorResponse"];
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
  delete_connector_api_v1_knowledge_bases__base_id__connectors__connector_id__delete: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        base_id: string;
        connector_id: string;
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
  test_connector_api_v1_knowledge_bases__base_id__connectors__connector_id__test_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        base_id: string;
        connector_id: string;
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
          "application/json": components["schemas"]["ConnectorTestResult"];
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
  sync_connector_api_v1_knowledge_bases__base_id__connectors__connector_id__sync_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        base_id: string;
        connector_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      202: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ConnectorResponse"];
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
  update_fields_api_v1_knowledge_bases__base_id__contents__content_id__fields_put: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        base_id: string;
        content_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ContentFieldsInput"];
      };
    };
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
  update_schedule_api_v1_knowledge_bases__base_id__contents__content_id__schedule_put: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        base_id: string;
        content_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ContentScheduleInput"];
      };
    };
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
  refresh_content_api_v1_knowledge_bases__base_id__contents__content_id__refresh_post: {
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
  list_prices_api_v1_models_prices_get: {
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
              [key: string]: number;
            };
          };
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
  list_agent_memories_api_v1_configs__config_id__memories_get: {
    parameters: {
      query?: {
        user_id?: string | null;
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
          "application/json": components["schemas"]["MemoryItem"][];
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
  forget_user_api_v1_configs__config_id__memories_delete: {
    parameters: {
      query: {
        user_id: string;
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
  delete_agent_memory_api_v1_configs__config_id__memories__memory_id__delete: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        config_id: string;
        memory_id: string;
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
  list_my_memories_api_v1_me_memories_get: {
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
          "application/json": components["schemas"]["MemoryItem"][];
        };
      };
    };
  };
  forget_me_api_v1_me_memories_delete: {
    parameters: {
      query?: never;
      header?: never;
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
    };
  };
  delete_my_memory_api_v1_me_memories__memory_id__delete: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        memory_id: string;
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
  get_reconciliation_api_v1_metrics_reconciliation_get: {
    parameters: {
      query?: {
        days?: number;
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
          "application/json": components["schemas"]["Reconciliation"];
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
  get_run_reviews_api_v1_runs__run_id__reviews_get: {
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
          "application/json": components["schemas"]["ReviewEntry"][];
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
