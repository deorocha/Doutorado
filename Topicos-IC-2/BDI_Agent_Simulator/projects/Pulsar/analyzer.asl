// analyzer.asl

// dispara inicialização ao carregar o agente
!start_analyzer.

// inicialização
+!start_analyzer <-
    .print("iniciado").

// recebe vitais, calcula score e risco e envia para coordinator e recommender
+vitals(PatientId, SampleId, HR, RR, Temp, SpO2, SBP, DBP, AVPU) <-
    .print("recebi vitais de ", PatientId, " amostra ", SampleId,
           " HR=", HR, " RR=", RR, " Temp=", Temp,
           " SpO2=", SpO2, " SBP=", SBP, " DBP=", DBP,
           " AVPU=", AVPU);
    !avpu_score(AVPU, AVPUScore);
    Score = AVPUScore;
    !classify_risk(Score, Risk);
    .print("paciente ", PatientId, " amostra ", SampleId,
           " Score=", Score, " risco=", Risk);
    .send(coordinator, tell, mews(PatientId, SampleId, Score, Risk));
    .send(recommender, tell, mews(PatientId, SampleId, Score, Risk)).

// conversão AVPU -> score numérico
+!avpu_score(a, ScoreAVPU) <- ScoreAVPU = 0.
+!avpu_score(v, ScoreAVPU) <- ScoreAVPU = 1.
+!avpu_score(p, ScoreAVPU) <- ScoreAVPU = 2.
+!avpu_score(u, ScoreAVPU) <- ScoreAVPU = 3.

// classificação de risco a partir do score
+!classify_risk(Score, Risk) : Score == 0 <- Risk = low.
+!classify_risk(Score, Risk) : Score == 1 <- Risk = moderate.
+!classify_risk(Score, Risk) : Score == 2 <- Risk = high.
+!classify_risk(Score, Risk) : Score == 3 <- Risk = high.
