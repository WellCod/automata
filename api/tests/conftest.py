import os

# O tracing do Agno instala um TracerProvider global, uma vez por processo, preso
# ao banco do primeiro app criado; depois disso os spans dos testes seguintes vão
# para um container já derrubado. Na suíte fica desligado: o teste real de spans
# roda num subprocesso (tests/test_traces.py).
os.environ.setdefault("TRACING_ENABLED", "false")
# O laço das suítes agendadas sobe junto com o app; os testes chamam o poll_once direto
os.environ.setdefault("EVAL_SCHEDULER_ENABLED", "false")
