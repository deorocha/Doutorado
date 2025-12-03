// ---------------------------------------------------------------------
// notifier.asl - Exibe recomendações recebidas do recommender
// Fonte: recommendation(Patient,Sample,Risk,Texto) [source(recommender)]
// ---------------------------------------------------------------------

+!init : true <- 
    .print("[notifier] iniciado").

// ------------------------------------------------------------
// Controle para não repetir cabeçalho para o mesmo paciente/amostra/risco
// ------------------------------------------------------------

// Primeiro recommendation desse Patient/Sample/Risk: mostra cabeçalho + bullet
+recommendation(Patient, Sample, Risk, Text)[source(recommender)] : 
    not header_shown(Patient, Sample, Risk) <- 
        .print("[LEITO ", Patient, 
               "] recomendações para amostra ", Sample, 
               " (risco=", Risk, ")"); 
        .print("[LEITO ", Patient, "] - ", Text);
        +header_shown(Patient, Sample, Risk).

// Demais recommendations do mesmo Patient/Sample/Risk: só bullet
+recommendation(Patient, Sample, Risk, Text)[source(recommender)] : 
    header_shown(Patient, Sample, Risk) <- 
        .print("[LEITO ", Patient, "] - ", Text).
