/**
 * SIRO Inmobiliaria - Catálogo de propiedades (módulo compartido)
 * Conexión a Supabase, etiquetas en castellano y utilidades usadas tanto
 * por el panel /admin como por las páginas públicas.
 *
 * La clave "publishable" es pública por diseño: la seguridad la ponen las
 * políticas RLS de supabase/schema.sql. Nunca poner aquí la secret/service_role.
 */
import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.117.2/+esm";

export const SUPABASE_URL = "https://wgqziotedvxbhghthkxx.supabase.co";
export const SUPABASE_KEY = "sb_publishable_fNO41kPE-5VK-coGeS-VOw_tOHZj3VX";
export const BUCKET = "propiedades";

export const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);

export const OPERACIONES = {
  venta: "Venta",
  alquiler: "Alquiler"
};

export const TIPOS = {
  piso: "Piso",
  atico: "Ático",
  duplex: "Dúplex",
  estudio: "Estudio",
  casa: "Casa",
  chalet: "Chalet",
  caserio: "Caserío",
  local: "Local comercial",
  oficina: "Oficina",
  garaje: "Garaje",
  trastero: "Trastero",
  terreno: "Terreno"
};

export const ESTADOS = {
  borrador: "Borrador",
  publicada: "Publicada",
  reservada: "Reservada",
  vendida: "Vendida",
  alquilada: "Alquilada"
};

export const CONSERVACION = {
  obra_nueva: "Obra nueva",
  buen_estado: "Buen estado",
  reformado: "Reformado",
  a_reformar: "A reformar"
};

export const CARACTERISTICAS = {
  ascensor: "Ascensor",
  garaje: "Plaza de garaje",
  trastero: "Trastero",
  terraza: "Terraza",
  balcon: "Balcón",
  jardin: "Jardín",
  piscina: "Piscina",
  calefaccion: "Calefacción",
  aire_acondicionado: "Aire acondicionado",
  exterior: "Exterior",
  vistas_mar: "Vistas al mar",
  amueblado: "Amueblado",
  cocina_equipada: "Cocina equipada",
  armarios_empotrados: "Armarios empotrados",
  porteria: "Portería",
  accesible: "Accesible"
};

export const CERTIFICADOS = {
  A: "A", B: "B", C: "C", D: "D", E: "E", F: "F", G: "G",
  en_tramite: "En trámite",
  exento: "Exento"
};

export const MUNICIPIOS = [
  "Pasaia", "Donostia-San Sebastián", "Errenteria", "Lezo", "Oiartzun",
  "Hondarribia", "Irun", "Astigarraga", "Hernani", "Lasarte-Oria", "Usurbil",
  "Urnieta", "Andoain", "Orio", "Zarautz", "Getaria", "Zumaia", "Tolosa",
  "Azpeitia", "Azkoitia", "Beasain", "Ordizia", "Zumarraga", "Legazpi",
  "Bergara", "Arrasate-Mondragón", "Eibar", "Elgoibar", "Deba", "Mutriku"
];

const precioFormat = new Intl.NumberFormat("es-ES", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
  useGrouping: "always"
});

export function formatPrecio(p) {
  if (p.precio_a_consultar || p.precio == null) return "Precio a consultar";
  return precioFormat.format(p.precio) + (p.operacion === "alquiler" ? "/mes" : "");
}

export function slugify(text) {
  return String(text || "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/ñ/g, "n")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80)
    .replace(/-+$/g, "");
}

/** El slug siempre termina en la referencia (…-siro-0007), que es lo que usa la ficha para buscarla. */
export function propertySlug(titulo, referencia) {
  return [slugify(titulo), slugify(referencia)].filter(Boolean).join("-");
}

export function publicUrl(p) {
  return `/propiedades/${p.slug}`;
}

export function imageUrl(path) {
  return `${SUPABASE_URL}/storage/v1/object/public/${BUCKET}/${path}`;
}

export function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
