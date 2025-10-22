// Crenças iniciais
pos(3,3).

// Comportamento reativo do incinerador
+!manter_posicao.

+lixo_para_incinerar : true <- 
    .print("R2: Incinerando lixo...");
    incinerate;
    .print("R2: Lixo incinerado com sucesso!");
    .print("R2: Aguardando próximo lixo...").
