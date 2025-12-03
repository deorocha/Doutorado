// ---------------------------------------------
// PatientCollector.asl - versão com limite de amostras
// ---------------------------------------------

// Número máximo de amostras a coletar
max_samples(10).

!start_collection.

// Inicialização: começa a coleta na amostra 1
+!start_collection : true <-
    .print("patient_collector iniciado");
    !loop_collect(1).

// Loop enquanto ainda não chegou na amostra final
+!loop_collect(Sample) : max_samples(Max) & Sample \== Max <-
    .print("enviando ação collect_vitals ao ambiente, amostra ", Sample);
    collect_vitals;
    .wait(10000);
    Next = Sample + 1;
    !loop_collect(Next).

// Última amostra: faz a coleta e não recursa mais
+!loop_collect(Sample) : max_samples(Max) & Sample = Max <-
    .print("enviando ação collect_vitals ao ambiente, amostra final ", Sample);
    collect_vitals;
    .wait(5000);
    .print("patient_collector: fim da coleta, total de amostras = ", Sample).

// ---------------------------------------------
// Percepções de vitais
// ---------------------------------------------

// Versão que realmente está sendo usada (vitals/9)
+vitals(PatientId, SampleId, HR, RR, Temp, SpO2, SBP, DBP, AVPU) <-
    .print("recebi vitais de ", PatientId,
           " amostra ", SampleId,
           " HR=", HR,
           " RR=", RR,
           " Temp=", Temp,
           " SpO2=", SpO2,
           " SBP=", SBP,
           " DBP=", DBP,
           " AVPU=", AVPU).

// Versão alternativa, caso no Java você passe o perfil também
+vitals(PatientId, SampleId, Profile, HR, RR, Temp, SpO2, SBP, DBP, AVPU) <-
    .print("recebi vitais de ", PatientId,
           " amostra ", SampleId,
           " perfil=", Profile,
           " HR=", HR,
           " RR=", RR,
           " Temp=", Temp,
           " SpO2=", SpO2,
           " SBP=", SBP,
           " DBP=", DBP,
           " AVPU=", AVPU).
