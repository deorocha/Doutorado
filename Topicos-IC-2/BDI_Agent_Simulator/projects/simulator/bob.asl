// Bob: papel Provider -> depende de Alice, contribui para softgoal
+!realizar_analise <-
    .print("Bob: realizando análise solicitada por Alice");
    !analisar_dados;
    send(alice,inform,analise_concluida).

+!analisar_dados <-
    .print("Bob: executando análise de dados (task)");
    .wait(200);
    .print("Bob: análise finalizada").

+!garantir_seguranca <-
    .print("Bob: softgoal segurança garantida").