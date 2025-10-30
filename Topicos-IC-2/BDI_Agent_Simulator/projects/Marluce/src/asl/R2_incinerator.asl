/* 
 * Agente R2 - O Incinerador
 * Arquivo: R2_incinerator.asl
 */

// --- CRENÇAS INICIAIS ---
// Crença de R2 sobre quantos ouros guardou
stored_gold(0).

// --- PLANOS (Reativos) ---
// R2 é um agente reativo. Ele espera por mensagens de R1.

// Plano 1: R1 entrega LIXO (garbage)
// Este plano é disparado quando a crença 'deliver(garbage)' é adicionada
+deliver(garbage)[source(R1)] <-
    .print("R2: Recebi LIXO de ", R1, ".");
    !incinerate. // Inicia o objetivo de incinerar

// Plano 2: R1 entrega OURO (gold)
// Este plano é disparado quando a crença 'deliver(gold)' é adicionada
+deliver(gold)[source(R1)] <-
    .print("R2: Recebi OURO de ", R1, ".");
    !store_gold. // Inicia o objetivo de guardar o ouro

// Sub-plano: Ação de incinerar
+!incinerate <-
    .print("R2: ...Lixo incinerado...").
    // Em um ambiente real, aqui ocorreria a ação no ambiente.

// Sub-plano: Ação de guardar ouro (atualizando a crença interna)
+!store_gold : stored_gold(N) <-
    -stored_gold(N);        // Remove a crença antiga (N)
    NewN = N + 1;           // Calcula o novo valor
    +stored_gold(NewN);     // Adiciona a nova crença (N+1)
    .print("R2: ...Ouro armazenado. Total guardado: ", NewN).