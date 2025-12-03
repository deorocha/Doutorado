// ---------------------------------------------------------------------
// coordinator.asl - Coordena mudanças de risco com base no MEWS
// Versão estável (sem loops, sem ações fantasmas no ambiente)
// ---------------------------------------------------------------------

// ---------------------------------------------------------------------
// Crenças iniciais: último risco conhecido de cada paciente
// (FICAM FORA DE QUALQUER PLANO!)
// ---------------------------------------------------------------------
last_risk(p1,  low).
last_risk(p2,  low).
last_risk(p3,  low).
last_risk(p4,  low).
last_risk(p5,  low).
last_risk(p6,  low).
last_risk(p7,  low).
last_risk(p8,  low).
last_risk(p9,  low).
last_risk(p10, low).

// Último MEWS recebido (apenas referência; começa tudo com score 0 low)
mews_latest(p1,  0, low).
mews_latest(p2,  0, low).
mews_latest(p3,  0, low).
mews_latest(p4,  0, low).
mews_latest(p5,  0, low).
mews_latest(p6,  0, low).
mews_latest(p7,  0, low).
mews_latest(p8,  0, low).
mews_latest(p9,  0, low).
mews_latest(p10, 0, low).

// ---------------------------------------------------------------------
// Inicialização (só log, sem mexer em crenças)
// ---------------------------------------------------------------------
+!init : true <- .print("coordinator iniciado.").

// ---------------------------------------------------------------------
// Recepção de MEWS vindo do analyzer
// analyzer envia: .send(coordinator, tell, mews(Patient, Sample, Score, Risk))
// Isso gera o evento +mews(...)
// ---------------------------------------------------------------------
+mews(Patient, Sample, Score, Risk) : true <- 
    .print("recebi mews de ", Patient, " amostra ", Sample, " Score=", Score, " risco=", Risk);
    -+mews_latest(Patient, Sample, Risk);
    !handle_risk(Patient, Sample, Score, Risk).

// ---------------------------------------------------------------------
// Tratamento de risco
// ---------------------------------------------------------------------

// Caso 1: risco atual é igual ao último registrado
+!handle_risk(Patient, Sample, Score, Risk) : last_risk(Patient, Risk) <- 
    .print("risco de ", Patient, " permanece ", Risk, " na amostra ", Sample, ".").

// Caso 2: risco mudou (OldRisk diferente de Risk)
+!handle_risk(Patient, Sample, Score, Risk) : last_risk(Patient, OldRisk) & OldRisk \== Risk <- 
    -+last_risk(Patient, Risk);
    !notify_risk_change(Patient, Sample, Score, OldRisk, Risk).

// Caso 3 (robusto): paciente sem last_risk conhecido ainda
+!handle_risk(Patient, Sample, Score, Risk) : not last_risk(Patient, _) <- 
    +last_risk(Patient, Risk);
    !notify_risk_change(Patient, Sample, Score, unknown, Risk).

// ---------------------------------------------------------------------
// Notificação de mudanças de risco
// ---------------------------------------------------------------------

// Mudança para HIGH: ESCALACAO
+!notify_risk_change(Patient, Sample, Score, OldRisk, high) : true <- 
    .print("ESCALACAO para risco alto de ", Patient, " na amostra ", Sample, " Score=", Score, " vindo de ", OldRisk);
    .send(notifier, tell, alert(Patient, Sample, Score, high));
    .send(notifier, tell, risk_trend(Patient, OldRisk, high)).

// Mudança para MODERATE
+!notify_risk_change(Patient, Sample, Score, OldRisk, moderate) : true <- 
    .print("risco moderado de ", Patient, " na amostra ", Sample, " Score=", Score, " vindo de ", OldRisk);
    .send(notifier, tell, alert(Patient, Sample, Score, moderate));
    .send(notifier, tell, risk_trend(Patient, OldRisk, moderate)).

// Mudança para LOW (resolução de risco)
+!notify_risk_change(Patient, Sample, Score, OldRisk, low) : true <- 
    .print("risco baixo de ", Patient, " na amostra ", Sample, " Score=", Score, " vindo de ", OldRisk);
    .send(notifier, tell, risk_resolved(Patient, Sample, Score, OldRisk, low)).
