// Dana: papel Worker -> depende de Bob, contribui com relatório
+!gerar_relatorio <-
    .print("Dana: aguardando análise de Bob");
    send(bob,request,enviar_dados);
    .wait(400);
    .print("Dana: gerando relatório (task)");
    send(alice,inform,relatorio_gerado).

+!garantir_clareza <-
    .print("Dana: softgoal clareza garantida").