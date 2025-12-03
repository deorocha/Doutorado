import jason.asSyntax.ASSyntax;
import jason.asSyntax.Literal;
import jason.asSyntax.NumberTermImpl;
import jason.asSyntax.Structure;
import jason.asSyntax.Term;
import jason.environment.Environment;

import java.util.HashMap;
import java.util.Map;
import java.util.Random;

public class HospitalEnv extends Environment {

    private Random random = new Random();

    // Perfis de paciente por leito (1..10)
    private Map<Integer, String> bedProfiles = new HashMap<Integer, String>();

    // Severidade apenas para perfis "unstable_deteriorating"
    private Map<Integer, Double> bedSeverity = new HashMap<Integer, Double>();

    // Contador de amostras por leito
    private Map<Integer, Integer> bedSamples = new HashMap<Integer, Integer>();

    @Override
    public void init(String[] args) {
        System.out.println("HospitalEnv iniciado.");

        // Configura os perfis conforme o simulador em Python
        bedProfiles.put(1, "baseline");
        bedProfiles.put(2, "baseline");
        bedProfiles.put(3, "baseline");
        bedProfiles.put(4, "baseline");
        bedProfiles.put(5, "stable_chronic");
        bedProfiles.put(6, "stable_chronic");
        bedProfiles.put(7, "stable_chronic");
        bedProfiles.put(8, "unstable");
        bedProfiles.put(9, "unstable_deteriorating");
        bedProfiles.put(10, "unstable_deteriorating");

        // Inicializa severidade e contador de amostras
        for (int bedId = 1; bedId <= 10; bedId++) {
            bedSamples.put(bedId, 0);
            String profile = bedProfiles.get(bedId);
            if ("unstable_deteriorating".equals(profile)) {
                bedSeverity.put(bedId, 0.0);
            }
        }
    }

    @Override
    public boolean executeAction(String agName, Structure act) {
        String functor = act.getFunctor();

        if ("collect_vitals".equals(functor)) {
            System.out.println("Ação recebida do agente " + agName + ": " + functor);
            System.out.println(" -> Ambiente: simulando coleta de sinais vitais dos pacientes.");

            // Mantemos só os vitais mais recentes como percepções
            clearPercepts("patient_collector");
            clearPercepts("analyzer");

            simulateAndSendAllBeds();
            return true;
        }

        return super.executeAction(agName, act);
    }

    private void simulateAndSendAllBeds() {
        for (int bedId = 1; bedId <= 10; bedId++) {
            String profile = bedProfiles.get(bedId);
            VitalSigns vs = generateReadingForBed(bedId, profile);

            // Atualiza contador de amostra por leito
            int sample = bedSamples.get(bedId) + 1;
            bedSamples.put(bedId, sample);

            String patientId = "p" + bedId;

            // Log no console (para facilitar visualização)
            System.out.println("[env] vitais de " + patientId +
                    " amostra " + sample +
                    " perfil=" + profile +
                    " HR=" + vs.heartRate +
                    " RR=" + vs.respRate +
                    " Temp=" + vs.temperature +
                    " SpO2=" + vs.spo2 +
                    " SBP=" + vs.systolic +
                    " DBP=" + vs.diastolic +
                    " AVPU=" + vs.avpu);

            // Cria percept vitals(Patient, Sample, HR, RR, Temp, SpO2, SBP, DBP, AVPU)
            try {
                Term pTerm = ASSyntax.createAtom(patientId);
                Term sTerm = new NumberTermImpl(sample);
                Term hrTerm = new NumberTermImpl(vs.heartRate);
                Term rrTerm = new NumberTermImpl(vs.respRate);
                Term tempTerm = new NumberTermImpl(vs.temperature);
                Term spo2Term = new NumberTermImpl(vs.spo2);
                Term sbpTerm = new NumberTermImpl(vs.systolic);
                Term dbpTerm = new NumberTermImpl(vs.diastolic);
                Term avpuTerm = ASSyntax.createAtom(String.valueOf(vs.avpu));

                Literal vitalsLit = ASSyntax.createLiteral(
                        "vitals",
                        pTerm, sTerm, hrTerm, rrTerm,
                        tempTerm, spo2Term, sbpTerm, dbpTerm, avpuTerm
                );

                // Envia o mesmo percept para patient_collector e analyzer
                addPercept("patient_collector", vitalsLit);
                addPercept("analyzer", vitalsLit);
            } catch (Exception e) {
                e.printStackTrace();
            }
        }
    }

    // ---------------------------
    // Estrutura auxiliar
    // ---------------------------

    private static class VitalSigns {
        int heartRate;
        int systolic;
        int diastolic;
        int respRate;
        double temperature;
        int spo2;
        char avpu;
    }

    // ---------------------------
    // Funções auxiliares
    // ---------------------------

    private double clamp(double value, double low, double high) {
        if (value < low) return low;
        if (value > high) return high;
        return value;
    }

    private char chooseAvpu(double pA, double pV, double pP, double pU) {
        double r = random.nextDouble();
        if (r <= pA) return 'a';
        if (r <= pA + pV) return 'v';
        if (r <= pA + pV + pP) return 'p';
        return 'u';
    }

    // ---------------------------
    // Geradores por perfil
    // ---------------------------

    private VitalSigns generateBaseline() {
        VitalSigns vs = new VitalSigns();
        vs.heartRate = (int) Math.round(random.nextGaussian() * 5 + 85);   // 75–95
        vs.systolic = (int) Math.round(random.nextGaussian() * 5 + 115);   // ~110–120
        vs.diastolic = (int) Math.round(random.nextGaussian() * 5 + 75);   // ~70–80
        vs.respRate = (int) Math.round(random.nextGaussian() * 2 + 17);    // 14–20
        vs.temperature = Math.round((random.nextGaussian() * 0.2 + 37.0) * 10.0) / 10.0;
        double spo2Raw = random.nextGaussian() * 1 + 97;
        vs.spo2 = (int) Math.round(clamp(spo2Raw, 94, 100));
        vs.avpu = chooseAvpu(0.98, 0.02, 0.0, 0.0);
        return vs;
    }

    private VitalSigns generateStableChronic() {
        VitalSigns vs = new VitalSigns();
        vs.heartRate = (int) Math.round(random.nextGaussian() * 5 + 100);  // 90–110
        vs.systolic = (int) Math.round(random.nextGaussian() * 7 + 105);   // 95–115
        vs.diastolic = (int) Math.round(random.nextGaussian() * 5 + 68);   // 60–75
        vs.respRate = (int) Math.round(random.nextGaussian() * 3 + 24);    // 18–30
        vs.temperature = Math.round((random.nextGaussian() * 0.2 + 37.8) * 10.0) / 10.0;
        double spo2Raw = random.nextGaussian() * 2 + 92;
        vs.spo2 = (int) Math.round(clamp(spo2Raw, 88, 96));
        vs.avpu = chooseAvpu(0.4, 0.6, 0.0, 0.0);
        return vs;
    }

    private VitalSigns generateUnstable() {
        VitalSigns vs = new VitalSigns();
        vs.heartRate = (int) Math.round(random.nextGaussian() * 7 + 125);   // 110–140
        vs.systolic = (int) Math.round(random.nextGaussian() * 8 + 85);     // 70–100
        vs.diastolic = (int) Math.round(random.nextGaussian() * 6 + 50);    // 40–60
        vs.respRate = (int) Math.round(random.nextGaussian() * 4 + 34);     // 26–42
        vs.temperature = Math.round((random.nextGaussian() * 0.3 + 39.2) * 10.0) / 10.0;
        double spo2Raw = random.nextGaussian() * 3 + 86;
        vs.spo2 = (int) Math.round(clamp(spo2Raw, 80, 92));
        vs.avpu = chooseAvpu(0.0, 0.2, 0.4, 0.4);
        return vs;
    }

    private VitalSigns generateUnstableDeteriorating(int bedId) {
        VitalSigns vs = new VitalSigns();

        Double sevObj = bedSeverity.get(bedId);
        double severity = (sevObj == null) ? 0.0 : sevObj.doubleValue();

        // Aumenta severidade a cada leitura
        severity = clamp(severity + 0.01, 0.0, 1.0);
        bedSeverity.put(bedId, severity);

        double s = severity;

        vs.heartRate = (int) Math.round(random.nextGaussian() * 5 + (115 + 20 * s));   // 115 → 135+
        vs.systolic = (int) Math.round(random.nextGaussian() * 6 + (95 - 25 * s));     // 95 → ~70
        vs.diastolic = (int) Math.round(random.nextGaussian() * 4 + (60 - 10 * s));    // 60 → ~50
        vs.respRate = (int) Math.round(random.nextGaussian() * 3 + (26 + 10 * s));     // 26 → 36+
        vs.temperature = Math.round(
                (random.nextGaussian() * 0.2 + (38.3 + 0.7 * s)) * 10.0
        ) / 10.0;
        double spo2Raw = random.nextGaussian() * 3 + (90 - 8 * s);
        vs.spo2 = (int) Math.round(clamp(spo2Raw, 78, 94));

        // Probabilidades AVPU variando com a gravidade
        char av;
        if (s < 0.3) {
            av = chooseAvpu(0.1, 0.5, 0.3, 0.1);
        } else if (s < 0.7) {
            av = chooseAvpu(0.0, 0.3, 0.4, 0.3);
        } else {
            av = chooseAvpu(0.0, 0.1, 0.3, 0.6);
        }
        vs.avpu = av;

        return vs;
    }

    private VitalSigns generateReadingForBed(int bedId, String profile) {
        if ("baseline".equals(profile)) {
            return generateBaseline();
        } else if ("stable_chronic".equals(profile)) {
            return generateStableChronic();
        } else if ("unstable".equals(profile)) {
            return generateUnstable();
        } else if ("unstable_deteriorating".equals(profile)) {
            return generateUnstableDeteriorating(bedId);
        } else {
            // fallback seguro: tratar como baseline
            return generateBaseline();
        }
    }
}
