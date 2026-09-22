# QMD Tools Explorer

Plugin para QGIS desenvolvido para pesquisa, visualização e exploração de imagens de sensoriamento remoto e dados geoespaciais relacionados ao território brasileiro.

O **QMD Tools Explorer** reúne ferramentas para consulta de catálogos STAC, exploração de produtos do **Brazil Data Cube (BDC)**, consulta de focos de calor do **Programa Queimadas** e visualização de camadas de referência diretamente no QGIS.

---

## Funcionalidades

### 🔎 Pesquisa de imagens

Permite pesquisar e explorar imagens de sensoriamento remoto utilizando catálogos STAC e serviços disponibilizados pelo Brazil Data Cube.

Principais recursos:

- Pesquisa de imagens utilizando **STAC API**;
- Integração com o **Brazil Data Cube (BDC)**;
- Pesquisa por coleção;
- Pesquisa por **Tile**;
- Pesquisa por **Órbita/Ponto**;
- Pesquisa utilizando a extensão atual do mapa;
- Filtro por intervalo de datas;
- Visualização dos resultados da pesquisa;
- Carregamento dos produtos diretamente no QGIS.

As imagens disponibilizadas pelo Brazil Data Cube são fornecidas em formato **Cloud Optimized GeoTIFF (COG)**, permitindo acesso eficiente aos dados em ambientes de computação em nuvem.

> **Observação:** os produtos COG disponibilizados pelo Brazil Data Cube utilizados pelo plugin estão relacionados ao território brasileiro.

---

### 🛰️ Satélites e produtos

O plugin permite explorar produtos derivados de diferentes missões de observação da Terra, incluindo:

- **Sentinel-2**;
- **Landsat 8**;
- **Landsat 9**;
- **CBERS-4**;
- **CBERS-4A**;
- **Amazônia-1**.

A disponibilidade de cada produto depende das coleções existentes nos catálogos consultados.

---

## 🗺️ Camadas de referência

O QMD Tools Explorer disponibiliza camadas de referência para auxiliar a interpretação e análise espacial dos dados.

Entre as camadas disponíveis estão:

- Google Hybrid;
- OpenStreetMap;
- Biomas;
- Estados;
- Amazônia Legal;
- Unidades de Conservação Federais;
- Unidades de Conservação Estaduais;
- Terras Indígenas;
- Assentamentos;
- Quilombos.

---

## 🔥 Focos de calor

O plugin também disponibiliza ferramentas relacionadas à consulta e visualização de focos de calor do **Programa Queimadas**.

Principais recursos:

- Consulta de focos de calor;
- Seleção de satélites;
- Consulta utilizando todos os satélites ou satélites de referência;
- Filtro por intervalo temporal;
- Filtro por estado;
- Filtro por órbita/ponto;
- Carregamento dos resultados diretamente no QGIS.

---

## 🌎 Área de interesse

As pesquisas podem utilizar a extensão espacial atualmente exibida no mapa do QGIS como área de interesse.

Esse recurso permite realizar consultas direcionadas a uma determinada região sem a necessidade de informar manualmente as coordenadas da área.

---

## 🛰️ Catálogos STAC

O plugin utiliza o padrão **STAC (SpatioTemporal Asset Catalog)** para consulta e descoberta de dados geoespaciais.

A utilização de STAC permite pesquisar informações considerando:

- localização espacial;
- intervalo temporal;
- coleção;
- propriedades dos produtos;
- recursos e ativos disponíveis.

Os resultados podem então ser analisados e carregados no projeto QGIS.

---

## 📦 Brazil Data Cube

O **Brazil Data Cube (BDC)** é uma iniciativa do Instituto Nacional de Pesquisas Espaciais (INPE) para disponibilização e exploração de dados de observação da Terra.

O QMD Tools Explorer utiliza os catálogos e produtos disponibilizados pelo BDC para facilitar a descoberta e utilização desses dados no QGIS.

Mais informações:

https://data.inpe.br/bdc

---

## 🖥️ Requisitos

- **QGIS 3.28 ou superior**;
- Conexão com a internet para acesso aos serviços e catálogos online;
- A disponibilidade dos dados depende dos serviços externos consultados pelo plugin.

O QMD Tools Explorer utiliza algumas bibliotecas Python adicionais:

- `pystac`;
- `pystac-client`;
- `shapely`;
- `requests`;
- `lxml`.

As bibliotecas `pystac` e `pystac-client` podem ser disponibilizadas pelo
plugin **STAC API Browser**, caso ele esteja instalado no ambiente QGIS.

O QMD Tools Explorer possui uma ferramenta de **verificação de dependências**
que permite verificar quais bibliotecas estão disponíveis no ambiente Python
do QGIS.

Caso alguma dependência esteja ausente, o plugin informa ao usuário quais
bibliotecas precisam ser instaladas.

### Instalação das dependências

No **Windows**, quando uma dependência estiver ausente, o QMD Tools Explorer
pode utilizar o `pip` para realizar a instalação no ambiente do usuário.

No **Linux**, algumas distribuições utilizam um ambiente Python gerenciado
pelo sistema operacional. Nesses casos, o QMD Tools Explorer não modifica
diretamente esse ambiente utilizando `pip`.

Quando uma dependência estiver ausente, o plugin orientará o usuário sobre
a instalação utilizando o gerenciador de pacotes do sistema.

Por exemplo, em sistemas baseados em Ubuntu/Debian:

```bash
sudo apt install python3-shapely

---

## 🚀 Instalação

### Repositório oficial do QGIS

Após a publicação no repositório oficial, o plugin poderá ser instalado diretamente pelo gerenciador de plugins do QGIS:

1. Abra o QGIS;
2. Acesse **Plugins → Gerenciar e Instalar Plugins**;
3. Pesquise por **QMD Tools Explorer**;
4. Selecione o plugin;
5. Clique em **Instalar Plugin**.

### Instalação manual

Durante o desenvolvimento, também é possível instalar uma versão do plugin a partir de um arquivo ZIP.

No QGIS:

**Plugins → Gerenciar e Instalar Plugins → Instalar a partir do ZIP**

Selecione o arquivo `.zip` correspondente ao plugin.

---

## 📖 Manual de utilização

Um manual básico de utilização está disponível no projeto e apresenta os principais procedimentos para pesquisa, visualização e exploração dos dados.

O manual aborda:

- instalação;
- abertura do plugin;
- pesquisa de imagens;
- consulta a catálogos STAC;
- utilização do Brazil Data Cube;
- área de interesse;
- visualização dos resultados;
- camadas de referência;
- consulta de focos de calor;
- solução de problemas.

---

## 👤 Autor

**Paulo W. P. da Cunha**

Instituto Nacional de Pesquisas Espaciais — INPE

---

## 📄 Licença

Este projeto é distribuído sob a licença **GNU General Public License v3.0 (GPL-3.0)**.

Consulte o arquivo [`LICENSE`](LICENSE) para obter os termos completos da licença.

---

## 📝 Registro de alterações

### 0.1.2 — 2026-09-22

- Primeira versão do QMD Tools Explorer;
- Pesquisa de imagens utilizando STAC API;
- Integração com produtos do Brazil Data Cube;
- Suporte a produtos Sentinel-2;
- Suporte a produtos Landsat 8 e 9;
- Suporte a produtos CBERS-4 e CBERS-4A;
- Suporte a produtos Amazônia-1;
- Pesquisa por Tile e Órbita/Ponto;
- Pesquisa utilizando a extensão atual do mapa;
- Consulta de focos de calor;
- Filtros temporais e espaciais para focos de calor;
- Camadas de referência para apoio à análise espacial.
