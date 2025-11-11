// Alice: papel Manager -> metas hard/soft + tarefas
!iniciar_sessao.
!alta_performance.

+!iniciar_sessao <-
    .print("Alice: sessão iniciada");
    send(bob,request,realizar_analise).

+!alta_performance <-
    .print("Alice: garantindo alta_performance (softgoal)");
    send(charlie,request,otimizar_codigo).

+!finalizar_projeto <-
    .print("Alice: projeto finalizado").
