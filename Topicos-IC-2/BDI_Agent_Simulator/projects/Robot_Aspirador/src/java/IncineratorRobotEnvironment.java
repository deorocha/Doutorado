import jason.asSyntax.*;
import jason.environment.Environment;
import jason.environment.grid.GridWorldModel;
import jason.environment.grid.GridWorldView;
import jason.environment.grid.Location;

import java.awt.Color;
import java.awt.Font;
import java.awt.Graphics;
import java.util.*;
import java.util.logging.Logger;

public class IncineratorRobotEnvironment extends Environment {

    public static final int GSize = 7;
    public static final int R1 = 0;
    public static final int R2 = 1;
    public static final int LIXO = 16;
    public static final int MOEDA = 32;

    static Logger logger = Logger.getLogger(IncineratorRobotEnvironment.class.getName());

    private GridWorldModel model;
    private GridWorldView view;
    private Map<String, List<String>> pathCache = new HashMap<>();

    // Classe para nós do A*
    static class Node implements Comparable<Node> {
        int x, y;
        double g, h, f;
        Node parent;
        String action;

        Node(int x, int y, double g, double h, Node parent, String action) {
            this.x = x;
            this.y = y;
            this.g = g;
            this.h = h;
            this.f = g + h;
            this.parent = parent;
            this.action = action;
        }

        @Override
        public int compareTo(Node other) {
            return Double.compare(this.f, other.f);
        }

        @Override
        public boolean equals(Object obj) {
            if (this == obj) return true;
            if (obj == null || getClass() != obj.getClass()) return false;
            Node node = (Node) obj;
            return x == node.x && y == node.y;
        }

        @Override
        public int hashCode() {
            return Objects.hash(x, y);
        }
    }

    @Override
    public void init(String[] args) {
        model = new GridWorldModel(GSize, GSize, 2);
        view = new GridWorldView(model, "Incinerator Robot with Pathfinding", 600) {
            @Override
            public void draw(Graphics g, int x, int y, int object) {
                if (object == LIXO) {
                    drawLixo(g, x, y);
                } else if (object == MOEDA) {
                    drawMoeda(g, x, y);
                }
            }
            
            @Override
            public void drawAgent(Graphics g, int x, int y, Color c, int id) {
                if (id == R1) {
                    c = Color.BLUE;
                    g.setColor(c);
                    g.fillRect(x * cellSizeW + 2, y * cellSizeH + 2, cellSizeW - 4, cellSizeH - 4);
                    g.setColor(Color.WHITE);
                    g.setFont(new Font("Arial", Font.BOLD, 12));
                    g.drawString("R1", x * cellSizeW + 10, y * cellSizeH + 20);
                } else if (id == R2) {
                    c = Color.RED;
                    g.setColor(c);
                    g.fillOval(x * cellSizeW + 2, y * cellSizeH + 2, cellSizeW - 4, cellSizeH - 4);
                    g.setColor(Color.WHITE);
                    g.setFont(new Font("Arial", Font.BOLD, 12));
                    g.drawString("R2", x * cellSizeW + 10, y * cellSizeH + 20);
                }
            }
            
            public void drawLixo(Graphics g, int x, int y) {
                g.setColor(Color.GREEN);
                g.fillRect(x * cellSizeW + 8, y * cellSizeH + 8, cellSizeW - 16, cellSizeH - 16);
                g.setColor(Color.BLACK);
                g.drawString("L", x * cellSizeW + 15, y * cellSizeH + 25);
            }
            
            public void drawMoeda(Graphics g, int x, int y) {
                g.setColor(Color.YELLOW);
                g.fillOval(x * cellSizeW + 8, y * cellSizeH + 8, cellSizeW - 16, cellSizeH - 16);
                g.setColor(Color.BLACK);
                g.drawString("$", x * cellSizeW + 15, y * cellSizeH + 25);
            }
        };
        
        // Posições iniciais
        model.setAgPos(R1, 0, 0);
        model.setAgPos(R2, 3, 3);
        
        // Adiciona lixos (R1 não sabe essas posições inicialmente)
        model.add(LIXO, 1, 2);
        model.add(LIXO, 3, 5);
        model.add(LIXO, 4, 4);
        model.add(LIXO, 6, 6);
        
        // Adiciona moeda (R1 não sabe essa posição inicialmente)
        model.add(MOEDA, 4, 5);
        
        updatePercepts();
    }

    @Override
    public boolean executeAction(String agName, Structure action) {
        boolean result = false;
        
        try {
            if (agName.equals("R1")) {
                if (action.getFunctor().equals("move")) {
                    String direction = action.getTerm(0).toString();
                    result = moveR1(direction);
                } else if (action.getFunctor().equals("pick_lixo")) {
                    result = pickLixo();
                } else if (action.getFunctor().equals("drop_lixo")) {
                    result = dropLixo();
                } else if (action.getFunctor().equals("pick_moeda")) {
                    result = pickMoeda();
                } else if (action.getFunctor().equals("calculate_path")) {
                    int fromX = (int)((NumberTerm)action.getTerm(0)).solve();
                    int fromY = (int)((NumberTerm)action.getTerm(1)).solve();
                    int toX = (int)((NumberTerm)action.getTerm(2)).solve();
                    int toY = (int)((NumberTerm)action.getTerm(3)).solve();
                    result = calculatePath(fromX, fromY, toX, toY);
                } else if (action.getFunctor().equals("follow_path")) {
                    result = followPath();
                }
            } else if (agName.equals("R2")) {
                if (action.getFunctor().equals("incinerate")) {
                    result = incinerateLixo();
                }
            }
            
            if (result) {
                updatePercepts();
                Thread.sleep(200);
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
        
        return result;
    }
    
    // Algoritmo A* para encontrar o menor caminho
    private List<String> findPath(int startX, int startY, int goalX, int goalY) {
        String cacheKey = startX + "," + startY + "->" + goalX + "," + goalY;
        if (pathCache.containsKey(cacheKey)) {
            return pathCache.get(cacheKey);
        }

        PriorityQueue<Node> openSet = new PriorityQueue<>();
        Set<String> closedSet = new HashSet<>();
        
        Node startNode = new Node(startX, startY, 0, heuristic(startX, startY, goalX, goalY), null, null);
        openSet.add(startNode);
        
        int[] dx = {-1, 1, 0, 0}; // left, right, up, down
        int[] dy = {0, 0, -1, 1};
        String[] directions = {"left", "right", "up", "down"};
        
        while (!openSet.isEmpty()) {
            Node current = openSet.poll();
            
            if (current.x == goalX && current.y == goalY) {
                // Reconstruir o caminho
                List<String> path = new ArrayList<>();
                Node node = current;
                while (node.parent != null) {
                    path.add(0, node.action);
                    node = node.parent;
                }
                pathCache.put(cacheKey, path);
                return path;
            }
            
            closedSet.add(current.x + "," + current.y);
            
            for (int i = 0; i < 4; i++) {
                int nx = current.x + dx[i];
                int ny = current.y + dy[i];
                
                if (nx >= 0 && nx < GSize && ny >= 0 && ny < GSize && model.isFree(nx, ny)) {
                    if (closedSet.contains(nx + "," + ny)) {
                        continue;
                    }
                    
                    double newG = current.g + 1;
                    double newH = heuristic(nx, ny, goalX, goalY);
                    Node neighbor = new Node(nx, ny, newG, newH, current, directions[i]);
                    
                    if (!openSet.contains(neighbor) || newG < neighbor.g) {
                        openSet.remove(neighbor);
                        openSet.add(neighbor);
                    }
                }
            }
        }
        
        // Se não encontrou caminho, retorna lista vazia
        return new ArrayList<>();
    }
    
    private double heuristic(int x1, int y1, int x2, int y2) {
        // Distância de Manhattan
        return Math.abs(x1 - x2) + Math.abs(y1 - y2);
    }
    
    private boolean calculatePath(int fromX, int fromY, int toX, int toY) {
        List<String> path = findPath(fromX, fromY, toX, toY);
        clearPercepts("R1");
        
        // Adiciona o caminho como percepção
        if (!path.isEmpty()) {
            for (int i = 0; i < path.size(); i++) {
                addPercept("R1", Literal.parseLiteral("caminho(" + i + "," + path.get(i) + ")"));
            }
            addPercept("R1", Literal.parseLiteral("caminho_disponivel"));
            addPercept("R1", Literal.parseLiteral("caminho_tamanho(" + path.size() + ")"));
        } else {
            addPercept("R1", Literal.parseLiteral("caminho_nao_encontrado"));
        }
        
        return true;
    }
    
    private boolean followPath() {
        clearPercepts("R1");
        
        // Obtém o próximo movimento do caminho
        for (int i = 0; i < 100; i++) { // Assume máximo 100 passos
            Literal step = getPercept("R1", Literal.parseLiteral("caminho(" + i + ",D)"));
            if (step != null) {
                String direction = step.getTerm(1).toString();
                if (moveR1(direction)) {
                    // Remove este passo e atualiza os próximos
                    removePercept("R1", step);
                    for (int j = i + 1; j < 100; j++) {
                        Literal nextStep = getPercept("R1", Literal.parseLiteral("caminho(" + j + ",D)"));
                        if (nextStep != null) {
                            removePercept("R1", nextStep);
                            addPercept("R1", Literal.parseLiteral("caminho(" + (j - 1) + "," + nextStep.getTerm(1) + ")"));
                        }
                    }
                    return true;
                }
            } else {
                break;
            }
        }
        
        addPercept("R1", Literal.parseLiteral("caminho_concluido"));
        return true;
    }
    
    private boolean moveR1(String direction) {
        Location r1 = model.getAgPos(R1);
        int x = r1.x, y = r1.y;
        
        switch (direction) {
            case "up": if (y > 0) y--; break;
            case "down": if (y < GSize-1) y++; break;
            case "left": if (x > 0) x--; break;
            case "right": if (x < GSize-1) x++; break;
        }
        
        if (model.isFree(x, y)) {
            model.setAgPos(R1, x, y);
            informAgsEnvironmentChanged();
            return true;
        }
        return false;
    }
    
    private boolean pickLixo() {
        Location r1 = model.getAgPos(R1);
        if (model.hasObject(LIXO, r1)) {
            model.remove(LIXO, r1);
            return true;
        }
        return false;
    }
    
    private boolean dropLixo() {
        Location r1 = model.getAgPos(R1);
        Location r2 = model.getAgPos(R2);
        
        // Só pode soltar lixo se estiver na posição do R2
        if (r1.x == r2.x && r1.y == r2.y) {
            // O lixo é imediatamente incinerado, não adicionamos de volta
            return true;
        }
        return false;
    }
    
    private boolean pickMoeda() {
        Location r1 = model.getAgPos(R1);
        if (model.hasObject(MOEDA, r1)) {
            model.remove(MOEDA, r1);
            return true;
        }
        return false;
    }
    
    private boolean incinerateLixo() {
        // R2 incinera qualquer lixo na sua posição
        Location r2 = model.getAgPos(R2);
        if (model.hasObject(LIXO, r2)) {
            model.remove(LIXO, r2);
            return true;
        }
        return false;
    }

    private void updatePercepts() {
        clearPercepts("R1");
        clearPercepts("R2");
        
        Location r1 = model.getAgPos(R1);
        Location r2 = model.getAgPos(R2);
        
        // Percepts para R1
        addPercept("R1", Literal.parseLiteral("pos(" + r1.x + "," + r1.y + ")"));
        addPercept("R1", Literal.parseLiteral("r2_pos(" + r2.x + "," + r2.y + ")"));
        
        // Verifica objetos na posição atual
        if (model.hasObject(LIXO, r1)) {
            addPercept("R1", Literal.parseLiteral("lixo_na_posicao"));
            addPercept("R1", Literal.parseLiteral("lixo_pos(" + r1.x + "," + r1.y + ")"));
        }
        
        if (model.hasObject(MOEDA, r1)) {
            addPercept("R1", Literal.parseLiteral("moeda_na_posicao"));
            addPercept("R1", Literal.parseLiteral("moeda_pos(" + r1.x + "," + r1.y + ")"));
        }
        
        // Verifica se está na posição do R2
        if (r1.x == r2.x && r1.y == r2.y) {
            addPercept("R1", Literal.parseLiteral("no_incinerador"));
        }
        
        // Percepts para R2
        addPercept("R2", Literal.parseLiteral("pos(" + r2.x + "," + r2.y + ")"));
        
        if (model.hasObject(LIXO, r2)) {
            addPercept("R2", Literal.parseLiteral("lixo_para_incinerar"));
        }
        
        informAgsEnvironmentChanged();
    }
}