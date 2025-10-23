// Crenças iniciais - R1 não sabe onde estão os lixos nem a moeda
pos(0,0).
r2_pos(3,3).

// Metas iniciais
!iniciar_limpeza.

// Estratégia de exploração sistemática com pathfinding
+!iniciar_limpeza <- 
    .print("Iniciando limpeza do ambiente - Modo Exploratório");
    .print("R1 não conhece as posições dos lixos e da moeda");
    .print("Explorando ambiente para encontrar lixos...");
    !explorar_sistematicamente.

// Exploração sistemática do grid
+!explorar_sistematicamente : 
    not todos_lixos_coletados &
    not exploracao_concluida
<- 
    ?pos(X,Y);
    .print("Explorando a partir de (",X,",",Y,")");
    
    // Encontra próxima posição não explorada
    !encontrar_proxima_posicao(X, Y, NextX, NextY);
    
    .print("Navegando para próxima posição de exploração (",NextX,",",NextY,")");
    !navegar_para(NextX, NextY);
    
    // Verifica se encontrou lixo na nova posição
    ?lixo_na_posicao;
    .print("Lixo encontrado durante exploração!");
    !processar_lixo.
    
+!explorar_sistematicamente : 
    not todos_lixos_coletados &
    not exploracao_concluida
<- 
    .print("Nenhum lixo encontrado nesta posição. Continuando exploração...");
    !explorar_sistematicamente.

+!explorar_sistematicamente : 
    todos_lixos_coletados &
    not moeda_coletada
<- 
    .print("Todos os lixos coletados! Procurando moeda...");
    !procurar_moeda.

// Encontrar próxima posição para explorar (busca em espiral)
+!encontrar_proxima_posicao(X, Y, NextX, NextY) : 
    true
<- 
    // Estratégia: exploração em espiral a partir da posição atual
    .findall(P, pos(PX,PY) & not visitado(PX,PY), PosicoesNaoVisitadas);
    
    if (PosicoesNaoVisitadas == []) {
        +exploracao_concluida;
        !encontrar_moeda_aleatoria(NextX, NextY)
    } else {
        // Encontra a posição mais próxima não visitada
        ?pos(CurrentX, CurrentY);
        !encontrar_mais_proxima(CurrentX, CurrentY, PosicoesNaoVisitadas, NextX, NextY)
    }.

+!encontrar_mais_proxima(CurrentX, CurrentY, [pos(X,Y)|T], BestX, BestY) :-
    !encontrar_mais_proxima(CurrentX, CurrentY, T, X, Y, BestX, BestY).

+!encontrar_mais_proxima(_, _, [], BestX, BestY, BestX, BestY).

+!encontrar_mais_proxima(CurrentX, CurrentY, [pos(X,Y)|T], CurrentBestX, CurrentBestY, BestX, BestY) :-
    DistanciaAtual is abs(CurrentX - X) + abs(CurrentY - Y),
    DistanciaBest is abs(CurrentX - CurrentBestX) + abs(CurrentY - CurrentBestY),
    (DistanciaAtual < DistanciaBest -> 
        !encontrar_mais_proxima(CurrentX, CurrentY, T, X, Y, BestX, BestY)
    ;
        !encontrar_mais_proxima(CurrentX, CurrentY, T, CurrentBestX, CurrentBestY, BestX, BestY)
    ).

// Navegação com pathfinding A*
+!navegar_para(DestX, DestY) : 
    pos(AtualX, AtualY)
<- 
    .print("Calculando melhor caminho de (",AtualX,",",AtualY,") para (",DestX,",",DestY,")");
    calculate_path(AtualX, AtualY, DestX, DestY);
    
    .wait(100); // Espera o cálculo do caminho
    
    ?caminho_disponivel;
    ?caminho_tamanho(Tamanho);
    .print("Caminho calculado com ",Tamanho," movimentos");
    
    !seguir_caminho(Tamanho);
    
    +visitado(DestX, DestY);
    .print("Chegou ao destino (",DestX,",",DestY,")").

+!seguir_caminho(0) <- 
    .print("Caminho concluído").

+!seguir_caminho(Tamanho) : 
    Tamanho > 0
<- 
    follow_path;
    .wait(200); // Espera entre movimentos
    NovoTamanho is Tamanho - 1;
    !seguir_caminho(NovoTamanho).

// Processamento quando encontra lixo
+!processar_lixo : 
    lixo_na_posicao &
    lixo_pos(LixoX, LixoY)
<- 
    .print("Processando lixo encontrado em (",LixoX,",",LixoY,")");
    pick_lixo;
    .print("Lixo coletado. Levando para incinerador...");
    
    ?r2_pos(IncX, IncY);
    !navegar_para(IncX, IncY);
    
    .print("Chegou ao incinerador. Depositando lixo...");
    drop_lixo;
    .print("Lixo depositado. Informando R2 para incinerar...");
    
    +lixo_coletado(LixoX, LixoY);
    !verificar_lixos_coletados.

// Verificar quantos lixos foram coletados
+!verificar_lixos_coletados :-
    .findall(L, lixo_coletado(X,Y), LixosColetados),
    length(LixosColetados, NumColetados),
    .print("Lixos coletados até agora: ", NumColetados),
    (NumColetados >= 4 -> 
        +todos_lixos_coletados;
        .print("Ainda há lixos para coletar. Continuando busca...")
    ).

// Busca pela moeda após limpeza
+!procurar_moeda : 
    not moeda_coletada
<- 
    .print("Procurando moeda...");
    ?pos(X,Y);
    
    // Se já sabe onde está a moeda, vai direto
    ?moeda_pos(MoedaX, MoedaY);
    .print("Moeda localizada em (",MoedaX,",",MoedaY,"). Navegando...");
    !navegar_para(MoedaX, MoedaY).

+!procurar_moeda : 
    not moeda_coletada &
    not moeda_pos(_,_)
<- 
    .print("Moeda ainda não encontrada. Continuando exploração...");
    !explorar_sistematicamente.

// Quando encontra a moeda
+moeda_na_posicao : 
    not moeda_coletada
<- 
    ?pos(X,Y);
    .print("Moeda encontrada em (",X,",",Y,")!");
    pick_moeda;
    +moeda_coletada;
    .print("Moeda coletada! Missão concluída com sucesso!");
    !finalizar.

// Busca aleatória por moeda se exploração concluída
+!encontrar_moeda_aleatoria(NextX, NextY) :-
    .random(0, 6, NextX),
    .random(0, 6, NextY),
    .print("Tentando posição aleatória (",NextX,",",NextY,") para encontrar moeda").

// Atualização de crenças de posição
+pos(X,Y) : true <- -pos(_,_); +pos(X,Y).

// Marcar posições como visitadas
+pos(X,Y) : not visitado(X,Y) <- +visitado(X,Y).

// Finalização
+!finalizar <- 
    .print("Missão completamente concluída! Todos os lixos coletados e moeda encontrada.").

// Plano de contingência para caminho não encontrado
+!navegar_para(DestX, DestY) : 
    caminho_nao_encontrado
<- 
    .print("Caminho não encontrado! Usando navegação alternativa...");
    !navegacao_alternativa(DestX, DestY).

// Navegação alternativa (fallback)
+!navegacao_alternativa(DestX, DestY) : 
    pos(AtualX, AtualY) &
    AtualX < DestX
<- 
    move(down);
    !navegacao_alternativa(DestX, DestY).

+!navegacao_alternativa(DestX, DestY) : 
    pos(AtualX, AtualY) &
    AtualX > DestX
<- 
    move(up);
    !navegacao_alternativa(DestX, DestY).

+!navegacao_alternativa(DestX, DestY) : 
    pos(AtualX, AtualY) &
    AtualY < DestY
<- 
    move(right);
    !navegacao_alternativa(DestX, DestY).

+!navegacao_alternativa(DestX, DestY) : 
    pos(AtualX, AtualY) &
    AtualY > DestY
<- 
    move(left);
    !navegacao_alternativa(DestX, DestY).

+!navegacao_alternativa(DestX, DestY) : 
    pos(DestX, DestY)
<- 
    .print("Chegou ao destino.").