// Código do nó "Vagas novas" do workflow principal (cópia pra facilitar a leitura;
// o que roda no n8n é o que está dentro do JSON em workflows/).
// Deixa passar só as vagas novas de verdade:
// 1. postadas hoje (ou desde ontem, na rodada das 6h00, que cobre a madrugada).
//    O Apify completa o resultado com vagas antigas quando a busca não tem vagas suficientes;
// 2. que ainda não foram processadas: a mesma vaga pode aparecer em duas buscas
//    ou em duas rodadas seguidas, por causa da folga de 5 min;
// 3. no máximo `maxVagas` por rodada (definido no nó Config).
// Os IDs ficam guardados nos dados estáticos do workflow por 30 dias.
// Obs.: o n8n só grava esses dados em execuções automáticas (workflow ativo),
// então em testes manuais as vagas não ficam marcadas como vistas.
const { maxVagas } = $('Config').first().json;
const primeiraDoDia = $now.hour === 6 && $now.minute < 30;
const desde = (primeiraDoDia ? $today.minus({ days: 1 }) : $today).toISODate();

const memoria = $getWorkflowStaticData('global');
const vistas = memoria.vagasVistas ?? {};
const agora = Date.now();
const TRINTA_DIAS = 30 * 24 * 60 * 60 * 1000;

for (const [id, quando] of Object.entries(vistas)) {
  if (agora - quando > TRINTA_DIAS) delete vistas[id];
}

const novas = [];
$input.all().forEach((item, i) => {
  const id = String(item.json.id ?? String(item.json.link ?? '').split('?')[0]);
  const postada = String(item.json.postedAt ?? '');
  // se a data vier num formato inesperado, não descarta (melhor uma vaga a mais que zero vagas)
  const antiga = /^\d{4}-\d{2}-\d{2}/.test(postada) && postada.slice(0, 10) < desde;
  if (novas.length >= maxVagas || !id || antiga || vistas[id]) return;
  vistas[id] = agora;
  novas.push({ json: item.json, pairedItem: { item: i } });
});

memoria.vagasVistas = vistas;
return novas;
