/* 
 * Agente R1 - Coletor responsável pela coleta
 * Arquivo: R1_collector.asl
 */

// Estado inicial: O agente começa com o objetivo de !start
!start.

// --- CRENÇAS INICIAIS ---
// Simulam o que R1 sabe sobre o mundo (sensores)
item_at(garbage, loc_A).
item_at(gold, loc_B).
item_at(garbage, loc_C).

// Onde está o incinerador R2 (mapa)
incinerator_at(loc_R2).

// Posição inicial de R1
at(home_R1).

// --- PLANOS ---

// Plano para o objetivo inicial: início da coleta
+!start : true <-
    .print("R1 (Coletor) iniciando... Procurando itens.");
    !collect_all. // Tenta atingir o objetivo de coletar tudo

// Plano principal: Coletar todos os itens
// 1. Se R1 encontrar um item (lixo ou ouro) e não estiver segurando nada
+!collect_all : item_at(Item, Loc) & not holding(_) <-
    .print("R1: Encontrei '", Item, "' em ", Loc, ". Indo até lá.");
    !goto(Loc);
    !pick(Item, Loc);
    !deliver_to_R2(Item).

// 2. Se não houver mais itens, o trabalho está feito
+!collect_all : not item_at(_, _) <-
    .print("R1: ----Todos os itens foram coletados---. Trabalho concluído =^.^=.").

// 3. Se R1 ainda está segurando algo (plano de recuperação, caso falhe no meio)
+!collect_all : holding(Item) <-
    .print("R1: Ainda estou segurando '", Item, "'. Preciso entregar.");
    !deliver_to_R2(Item).

// Sub-plano: Ir para um local
+!goto(Loc) : at(MyLoc) & MyLoc \== Loc <-
    -at(MyLoc); // Remove a crença da localização antiga
    +at(Loc);   // Adiciona a crença da nova localização (atualiza o mapa)
    .print("R1: Movi de ", MyLoc, " para ", Loc).

+!goto(Loc) : at(Loc) <-
    .print("R1: Já estou em ", Loc).

// Sub-plano: coletar um item
+!pick(Item, Loc) : at(Loc) & item_at(Item, Loc) <-
    -item_at(Item, Loc); // Remove a crença do item no local (ação de coletar)
    +holding(Item);      // Adiciona a crença de estar segurando
    .print("R1: Coletei '", Item, "'.").

+!pick(Item, Loc) : not at(Loc) <-
    .print("R1: Não posso coletar '", Item, "', não estou em ", Loc, ".");
    !goto(Loc);
    !pick(Item, Loc).

// Sub-plano: Entregar para R2
// 1. Se não estou no local do incinerador, vou até lá
+!deliver_to_R2(Item) : holding(Item) & incinerator_at(LocR2) & at(MyLoc) & MyLoc \== LocR2 <-
    .print("R1: Indo até R2 em ", LocR2, " para entregar '", Item, "'.");
    !goto(LocR2);
    !deliver_to_R2(Item). // Tenta entregar novamente quando chegar lá

// 2. Se estou segurando o item E estou no local do incinerador
+!deliver_to_R2(Item) : holding(Item) & incinerator_at(LocR2) & at(LocR2) <-
    .print("R1: Entregando '", Item, "' para R2.");
    .send(R2, tell, deliver(Item)); // Envia a mensagem para R2
    -holding(Item);                 // Não estou mais segurando
    !collect_all.                   // Procura o próximo item