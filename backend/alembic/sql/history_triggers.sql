-- Recovered from the inspected PostgreSQL schema. Applied only on a new empty database.
CREATE OR REPLACE FUNCTION public.atualizar_data_modificacao()
RETURNS trigger LANGUAGE plpgsql AS $function$
BEGIN
    NEW.atualizado_em = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION public.registrar_historico_lead()
RETURNS trigger LANGUAGE plpgsql AS $function$
BEGIN
    IF OLD.fase IS DISTINCT FROM NEW.fase THEN
        INSERT INTO historico_leads (lead_id, fase_anterior, fase_nova, movimentado_em)
        VALUES (OLD.id, OLD.fase, NEW.fase, CURRENT_TIMESTAMP);
    END IF;
    NEW.atualizado_em = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$function$;

CREATE TRIGGER trigger_atualizar_clientes BEFORE UPDATE ON clientes FOR EACH ROW EXECUTE FUNCTION public.atualizar_data_modificacao();
CREATE TRIGGER trigger_historico_lead BEFORE UPDATE ON leads FOR EACH ROW EXECUTE FUNCTION public.registrar_historico_lead();
CREATE TRIGGER trigger_atualizar_metas BEFORE UPDATE ON metas FOR EACH ROW EXECUTE FUNCTION public.atualizar_data_modificacao();
CREATE TRIGGER trigger_atualizar_projetos BEFORE UPDATE ON projetos FOR EACH ROW EXECUTE FUNCTION public.atualizar_data_modificacao();
CREATE TRIGGER trigger_atualizar_usuarios BEFORE UPDATE ON usuarios FOR EACH ROW EXECUTE FUNCTION public.atualizar_data_modificacao();
