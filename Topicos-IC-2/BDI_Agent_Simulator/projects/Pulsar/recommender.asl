// ---------------------------------------------------------------------
// recommender.asl - Gera recomendações a partir de MEWS e risco
// Fonte: analyzer -> mews(Patient,Sample,Score,Risk)
// Saída: recommendation(Patient,Sample,Risk,Texto) para notifier
// ---------------------------------------------------------------------

// Perfis de exemplo (ajuste depois)
patient_profile(p1,  adult).
patient_profile(p2,  adult).
patient_profile(p3,  adult).
patient_profile(p4,  adult).
patient_profile(p5,  chronic).
patient_profile(p6,  chronic).
patient_profile(p7,  chronic).
patient_profile(p8,  adult).
patient_profile(p9,  adult).
patient_profile(p10, adult).

+!init : true <- 
    .print("recommender iniciado.").

// ---------------------------------------------------------------------
// Entrada principal: mews vindo do analyzer
// ---------------------------------------------------------------------

// Caso com perfil conhecido
+mews(Patient, Sample, Score, Risk)[source(analyzer)] : patient_profile(Patient, Type) <- 
    .print("recebi mews de ", Patient, " amostra ", Sample, 
           " Score=", Score, " risco=", Risk, " perfil=", Type);
    !generate_recommendations(Patient, Sample, Score, Risk, Type).

// Caso sem perfil conhecido
+mews(Patient, Sample, Score, Risk)[source(analyzer)] : not patient_profile(Patient, _) <- 
    .print("recebi mews de ", Patient, " amostra ", Sample, 
           " Score=", Score, " risco=", Risk, " perfil desconhecido");
    !generate_recommendations_generic(Patient, Sample, Score, Risk).

// ---------------------------------------------------------------------
// Geração de recomendações por risco + perfil
// ---------------------------------------------------------------------

// HIGH - adulto
+!generate_recommendations(Patient, Sample, Score, high, adult) : true <- 
    .send(notifier, tell, recommendation(Patient, Sample, high, "Avaliação médica imediata em até 5 minutos.")); 
    .send(notifier, tell, recommendation(Patient, Sample, high, "Monitorar sinais vitais a cada 5 minutos.")); 
    .send(notifier, tell, recommendation(Patient, Sample, high, "Preparar acesso venoso e oxigênio suplementar se disponível.")); 
    .send(notifier, tell, recommendation(Patient, Sample, high, "Considerar transferência para leito com maior monitorização.")).

// HIGH - crônico
+!generate_recommendations(Patient, Sample, Score, high, chronic) : true <- 
    .send(notifier, tell, recommendation(Patient, Sample, high, "Avaliação médica imediata focando nas comorbidades.")); 
    .send(notifier, tell, recommendation(Patient, Sample, high, "Monitorar sinais vitais e glicemia (se aplicável) a cada 5 minutos.")); 
    .send(notifier, tell, recommendation(Patient, Sample, high, "Rever medicações em uso e possíveis interações.")); 
    .send(notifier, tell, recommendation(Patient, Sample, high, "Considerar suporte avançado e leito monitorizado.")).

// HIGH - genérico (outros perfis)
+!generate_recommendations(Patient, Sample, Score, high, Type) : 
    Type \== adult & Type \== chronic <- 
    .send(notifier, tell, recommendation(Patient, Sample, high, "Risco alto: avaliação médica imediata e monitorização intensiva.")).

// MODERATE - adulto
+!generate_recommendations(Patient, Sample, Score, moderate, adult) : true <- 
    .send(notifier, tell, recommendation(Patient, Sample, moderate, "Comunicar médico responsável em até 15 minutos.")); 
    .send(notifier, tell, recommendation(Patient, Sample, moderate, "Repetir sinais vitais em 15–30 minutos.")); 
    .send(notifier, tell, recommendation(Patient, Sample, moderate, "Observar padrão respiratório, dor e nível de consciência.")).

// MODERATE - crônico
+!generate_recommendations(Patient, Sample, Score, moderate, chronic) : true <- 
    .send(notifier, tell, recommendation(Patient, Sample, moderate, "Risco moderado em paciente crônico: avisar médico em até 15 minutos.")); 
    .send(notifier, tell, recommendation(Patient, Sample, moderate, "Repetir sinais vitais em 15–30 minutos, com atenção especial a SpO2 e PA.")); 
    .send(notifier, tell, recommendation(Patient, Sample, moderate, "Rever plano terapêutico e necessidade de ajustes.")).

// MODERATE - genérico
+!generate_recommendations(Patient, Sample, Score, moderate, Type) : 
    Type \== adult & Type \== chronic <- 
    .send(notifier, tell, recommendation(Patient, Sample, moderate, "Risco moderado: comunicar médico em até 15 minutos e repetir sinais vitais em 15–30 minutos.")).

// LOW - qualquer perfil
+!generate_recommendations(Patient, Sample, Score, low, Type) : true <- 
    .send(notifier, tell, recommendation(Patient, Sample, low, "Risco baixo: manter monitorização de rotina conforme protocolo local.")); 
    .send(notifier, tell, recommendation(Patient, Sample, low, "Registrar evolução em prontuário e manter observação clínica.")).

// ---------------------------------------------------------------------
// Versão genérica (sem perfil conhecido)
// ---------------------------------------------------------------------

+!generate_recommendations_generic(Patient, Sample, Score, high) : true <- 
    .send(notifier, tell, recommendation(Patient, Sample, high, "Risco alto: avaliação médica imediata e monitorização intensiva.")).

+!generate_recommendations_generic(Patient, Sample, Score, moderate) : true <- 
    .send(notifier, tell, recommendation(Patient, Sample, moderate, "Risco moderado: comunicar médico em até 15 minutos e repetir sinais vitais em 15–30 minutos.")).

+!generate_recommendations_generic(Patient, Sample, Score, low) : true <- 
    .send(notifier, tell, recommendation(Patient, Sample, low, "Risco baixo: manter monitorização de rotina.")).
