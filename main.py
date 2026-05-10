import discord
from discord import app_commands
import json
import os
from keep_alive import keep_alive

TOKEN = "COLOQUE_SEU_TOKEN_AQUI"

PENALIDADES = {
    "leve": 2,
    "media": 4,
    "grave": 6
}

def carregar_dados():
    if os.path.exists("condicoes.json"):
        with open("condicoes.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def salvar_dados(dados):
    with open("condicoes.json", "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

def pegar_penalidade(gravidade):
    return PENALIDADES.get(gravidade.lower(), 0)

def calcular_penalidade_pilar(personagem, pilar):
    if pilar not in personagem:
        return 0, []
    total = 0
    detalhes = []
    for condicao in personagem[pilar]:
        if not condicao.get("animo", False):
            p = pegar_penalidade(condicao["gravidade"])
            total += p
            detalhes.append(f"{condicao['nome']} (-{p})")
    return total, detalhes

def contar_condicoes_ativas(personagem, pilar):
    if pilar not in personagem:
        return 0
    return sum(1 for c in personagem[pilar] if not c.get("animo", False))

class QuimeraBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.dados = carregar_dados()
    
    async def setup_hook(self):
        await self.tree.sync()
        print("Quimera Condicoes online!")

bot = QuimeraBot()

# ============================================
# COMANDO: /criar_personagem
# ============================================

@bot.tree.command(name="criar_personagem", description="Cria um novo personagem no sistema")
@app_commands.describe(nome="Nome do personagem")
async def criar_personagem(interaction: discord.Interaction, nome: str):
    nome = nome.lower()
    
    if nome in bot.dados:
        await interaction.response.send_message(f"Personagem **{nome.title()}** ja existe.", ephemeral=True)
        return
    
    bot.dados[nome] = {
        "corpo": [],
        "mente": [],
        "alma": [],
        "animo_usados": 0,
        "animo_max": 3
    }
    salvar_dados(bot.dados)
    await interaction.response.send_message(f"Personagem **{nome.title()}** criado com sucesso!")

# ============================================
# COMANDO: /adicionar
# ============================================

@bot.tree.command(name="adicionar", description="Adiciona uma condicao ao personagem")
@app_commands.describe(
    nome_condicao="Nome da condicao (ex: Costela Quebrada)"
)
@app_commands.choices(
    gravidade=[
        app_commands.Choice(name="Leve (-2)", value="leve"),
        app_commands.Choice(name="Media (-4)", value="media"),
        app_commands.Choice(name="Grave (-6)", value="grave")
    ],
    pilar=[
        app_commands.Choice(name="Corpo", value="corpo"),
        app_commands.Choice(name="Mente", value="mente"),
        app_commands.Choice(name="Alma", value="alma")
    ]
)
async def adicionar(
    interaction: discord.Interaction,
    nome_condicao: str,
    gravidade: app_commands.Choice[str],
    pilar: app_commands.Choice[str]
):
    # Pegar o personagem de uma lista
    personagens = list(bot.dados.keys())
    if not personagens:
        await interaction.response.send_message("Nenhum personagem criado. Use /criar_personagem primeiro.", ephemeral=True)
        return
    
    # Criar menu de selecao de personagem
    options = [discord.SelectOption(label=p.title(), value=p) for p in personagens]
    
    select = discord.ui.Select(
        placeholder="Escolha o personagem...",
        options=options,
        custom_id="select_personagem"
    )
    
    async def select_callback(interaction2: discord.Interaction):
        personagem = select.values[0]
        pilar_valor = pilar.value
        gravidade_valor = gravidade.value
        
        bot.dados[personagem][pilar_valor].append({
            "nome": nome_condicao,
            "gravidade": gravidade_valor,
            "animo": False
        })
        salvar_dados(bot.dados)
        
        p = pegar_penalidade(gravidade_valor)
        await interaction2.response.send_message(
            f"**{nome_condicao}** adicionada a **{personagem.title()}**\n"
            f"Pilar: {pilar_valor.title()} | Gravidade: {gravidade_valor.title()} | Penalidade: -{p}"
        )
    
    select.callback = select_callback
    view = discord.ui.View()
    view.add_item(select)
    
    await interaction.response.send_message("Escolha o personagem:", view=view, ephemeral=True)

# ============================================
# COMANDO: /remover
# ============================================

@bot.tree.command(name="remover", description="Remove uma condicao do personagem")
async def remover(interaction: discord.Interaction):
    personagens = list(bot.dados.keys())
    if not personagens:
        await interaction.response.send_message("Nenhum personagem criado.", ephemeral=True)
        return
    
    # Menu: escolher personagem
    options_personagem = [discord.SelectOption(label=p.title(), value=p) for p in personagens]
    
    select_personagem = discord.ui.Select(
        placeholder="1. Escolha o personagem...",
        options=options_personagem,
        custom_id="remover_personagem"
    )
    
    async def personagem_callback(interaction2: discord.Interaction):
        personagem = select_personagem.values[0]
        
        # Menu: escolher condicao
        todas_condicoes = []
        for pilar in ["corpo", "mente", "alma"]:
            for c in bot.dados[personagem][pilar]:
                todas_condicoes.append((c["nome"], pilar))
        
        if not todas_condicoes:
            await interaction2.response.send_message(f"**{personagem.title()}** nao tem condicoes para remover.", ephemeral=True)
            return
        
        options_condicao = []
        for nome, p in todas_condicoes:
            label = f"{nome} ({p})"
            if len(label) > 100:
                label = label[:97] + "..."
            options_condicao.append(discord.SelectOption(label=label, value=f"{nome}|||{p}"))
        
        select_condicao = discord.ui.Select(
            placeholder="2. Escolha a condicao para remover...",
            options=options_condicao,
            custom_id="remover_condicao"
        )
        
        async def condicao_callback(interaction3: discord.Interaction):
            valor = select_condicao.values[0]
            nome_cond, pilar_cond = valor.split("|||")
            
            for c in bot.dados[personagem][pilar_cond]:
                if c["nome"].lower() == nome_cond.lower():
                    if c.get("animo", False):
                        bot.dados[personagem]["animo_usados"] = max(0, bot.dados[personagem].get("animo_usados", 0) - 1)
                    bot.dados[personagem][pilar_cond].remove(c)
                    break
            
            salvar_dados(bot.dados)
            await interaction3.response.send_message(f"**{nome_cond}** removida de **{personagem.title()}**.")
        
        select_condicao.callback = condicao_callback
        view2 = discord.ui.View()
        view2.add_item(select_condicao)
        
        await interaction2.response.send_message("Agora escolha a condicao:", view=view2, ephemeral=True)
    
    select_personagem.callback = personagem_callback
    view1 = discord.ui.View()
    view1.add_item(select_personagem)
    
    await interaction.response.send_message("Remover condicao:", view=view1, ephemeral=True)

# ============================================
# COMANDO: /listar
# ============================================

@bot.tree.command(name="listar", description="Lista todas as condicoes de um personagem")
async def listar(interaction: discord.Interaction):
    personagens = list(bot.dados.keys())
    if not personagens:
        await interaction.response.send_message("Nenhum personagem criado.", ephemeral=True)
        return
    
    options = [discord.SelectOption(label=p.title(), value=p) for p in personagens]
    
    select = discord.ui.Select(
        placeholder="Escolha o personagem...",
        options=options,
        custom_id="listar_personagem"
    )
    
    async def callback(interaction2: discord.Interaction):
        personagem = select.values[0]
        animo_max = bot.dados[personagem].get("animo_max", 3)
        animo_usados = bot.dados[personagem].get("animo_usados", 0)
        animo_disponivel = animo_max - animo_usados
        
        # Contar animo ocupado corretamente
        msg = f"**Condicoes de {personagem.title()}**\n"
        msg += f"Animo: {animo_disponivel}/{animo_max} disponivel\n\n"
        
        tem_condicao = False
        
        for pilar in ["corpo", "mente", "alma"]:
            condicoes = bot.dados[personagem][pilar]
            if condicoes:
                tem_condicao = True
                total, _ = calcular_penalidade_pilar(bot.dados[personagem], pilar)
                msg += f"**{pilar.upper()}** -- Penalidade: -{total}\n"
                
                for c in condicoes:
                    if c.get("animo", False):
                        msg += f"  [ANIMO] {c['nome']} ({c['gravidade'].title()})\n"
                    else:
                        msg += f"  {c['nome']} ({c['gravidade'].title()}, -{pegar_penalidade(c['gravidade'])})\n"
                msg += "\n"
        
        if not tem_condicao:
            msg += "Nenhuma condicao ativa."
        
        await interaction2.response.send_message(msg)
    
    select.callback = callback
    view = discord.ui.View()
    view.add_item(select)
    
    await interaction.response.send_message("Escolha o personagem:", view=view, ephemeral=True)

# ============================================
# COMANDO: /penalidade
# ============================================

@bot.tree.command(name="penalidade", description="Calcula a penalidade para um pilar")
@app_commands.choices(
    pilar=[
        app_commands.Choice(name="Corpo", value="corpo"),
        app_commands.Choice(name="Mente", value="mente"),
        app_commands.Choice(name="Alma", value="alma")
    ]
)
async def penalidade(interaction: discord.Interaction, pilar: app_commands.Choice[str]):
    personagens = list(bot.dados.keys())
    if not personagens:
        await interaction.response.send_message("Nenhum personagem criado.", ephemeral=True)
        return
    
    options = [discord.SelectOption(label=p.title(), value=p) for p in personagens]
    
    select = discord.ui.Select(
        placeholder="Escolha o personagem...",
        options=options,
        custom_id="penalidade_personagem"
    )
    
    pilar_valor = pilar.value
    
    async def callback(interaction2: discord.Interaction):
        personagem = select.values[0]
        total, detalhes = calcular_penalidade_pilar(bot.dados[personagem], pilar_valor)
        
        if not detalhes:
            await interaction2.response.send_message(
                f"**{personagem.title()}** -- Pilar {pilar_valor.title()}: **0**\n"
                f"Nenhuma condicao ativa."
            )
        else:
            msg = f"**{personagem.title()}** -- Pilar {pilar_valor.title()}: **-{total}**\n"
            for d in detalhes:
                msg += f"  {d}\n"
            await interaction2.response.send_message(msg)
    
    select.callback = callback
    view = discord.ui.View()
    view.add_item(select)
    
    await interaction.response.send_message("Escolha o personagem:", view=view, ephemeral=True)

# ============================================
# COMANDO: /animo
# ============================================

@bot.tree.command(name="animo", description="Gerencia o Animo de Absorcao")
@app_commands.choices(
    acao=[
        app_commands.Choice(name="Ver Animo disponivel", value="ver"),
        app_commands.Choice(name="Usar Animo (congelar condicao)", value="usar"),
        app_commands.Choice(name="Liberar Animo (apos estabilizacao)", value="liberar")
    ]
)
async def animo(interaction: discord.Interaction, acao: app_commands.Choice[str]):
    personagens = list(bot.dados.keys())
    if not personagens:
        await interaction.response.send_message("Nenhum personagem criado.", ephemeral=True)
        return
    
    acao_valor = acao.value
    
    if acao_valor == "ver":
        options = [discord.SelectOption(label=p.title(), value=p) for p in personagens]
        select = discord.ui.Select(
            placeholder="Escolha o personagem...",
            options=options,
            custom_id="animo_ver"
        )
        async def callback(interaction2: discord.Interaction):
            personagem = select.values[0]
            animo_max = bot.dados[personagem].get("animo_max", 3)
            animo_usados = bot.dados[personagem].get("animo_usados", 0)
            animo_disponivel = animo_max - animo_usados
            await interaction2.response.send_message(
                f"**{personagem.title()}** -- Animo: {animo_disponivel}/{animo_max} disponivel"
            )
        select.callback = callback
        view = discord.ui.View()
        view.add_item(select)
        await interaction.response.send_message("Escolha o personagem:", view=view, ephemeral=True)
        return
    
    # Para usar/liberar: menu de personagem e depois menu de condicao
    options_personagem = [discord.SelectOption(label=p.title(), value=p) for p in personagens]
    
    select_p = discord.ui.Select(
        placeholder="1. Escolha o personagem...",
        options=options_personagem,
        custom_id="animo_personagem"
    )
    
    async def p_callback(interaction2: discord.Interaction):
        personagem = select_p.values[0]
        
        # Listar condicoes validas
        condicoes_validas = []
        for pilar in ["corpo", "mente", "alma"]:
            for c in bot.dados[personagem][pilar]:
                if acao_valor == "usar" and c["gravidade"] == "grave":
                    continue  # Grave nao pode ser congelada
                if acao_valor == "usar" and c.get("animo", False):
                    continue  # Ja esta congelada
                if acao_valor == "liberar" and not c.get("animo", False):
                    continue  # Nao esta congelada
                condicoes_validas.append((c["nome"], pilar))
        
        if not condicoes_validas:
            if acao_valor == "usar":
                await interaction2.response.send_message("Nenhuma condicao disponivel para congelar (Graves nao podem, e condicoes ja congeladas nao contam).", ephemeral=True)
            else:
                await interaction2.response.send_message("Nenhuma condicao congelada para liberar.", ephemeral=True)
            return
        
        options_cond = []
        for nome, p in condicoes_validas:
            label = f"{nome} ({p})"
            if len(label) > 100:
                label = label[:97] + "..."
            options_cond.append(discord.SelectOption(label=label, value=f"{nome}|||{p}"))
        
        select_c = discord.ui.Select(
            placeholder="2. Escolha a condicao...",
            options=options_cond,
            custom_id="animo_condicao"
        )
        
        async def c_callback(interaction3: discord.Interaction):
            valor = select_c.values[0]
            nome_cond, pilar_cond = valor.split("|||")
            
            for c in bot.dados[personagem][pilar_cond]:
                if c["nome"].lower() == nome_cond.lower():
                    if acao_valor == "usar":
                        animo_usados = bot.dados[personagem].get("animo_usados", 0)
                        animo_max = bot.dados[personagem].get("animo_max", 3)
                        if animo_usados >= animo_max:
                            await interaction3.response.send_message("Animo esgotado.", ephemeral=True)
                            return
                        c["animo"] = True
                        bot.dados[personagem]["animo_usados"] = animo_usados + 1
                        salvar_dados(bot.dados)
                        novo_disponivel = animo_max - (animo_usados + 1)
                        await interaction3.response.send_message(
                            f"**{nome_cond}** congelada no Animo!\n"
                            f"Animo restante: {novo_disponivel}/{animo_max}"
                        )
                    else:  # liberar
                        c["animo"] = False
                        animo_usados = bot.dados[personagem].get("animo_usados", 0)
                        bot.dados[personagem]["animo_usados"] = max(0, animo_usados - 1)
                        salvar_dados(bot.dados)
                        novo_disponivel = bot.dados[personagem]["animo_max"] - bot.dados[personagem]["animo_usados"]
                        await interaction3.response.send_message(
                            f"**{nome_cond}** liberada do Animo.\n"
                            f"Animo disponivel: {novo_disponivel}/{bot.dados[personagem]['animo_max']}"
                        )
                    break
        
        select_c.callback = c_callback
        view2 = discord.ui.View()
        view2.add_item(select_c)
        await interaction2.response.send_message("Escolha a condicao:", view=view2, ephemeral=True)
    
    select_p.callback = p_callback
    view1 = discord.ui.View()
    view1.add_item(select_p)
    await interaction.response.send_message("Gerenciar Animo:", view=view1, ephemeral=True)

# ============================================
# COMANDO: /status
# ============================================

@bot.tree.command(name="status", description="Resumo completo do personagem")
async def status(interaction: discord.Interaction):
    personagens = list(bot.dados.keys())
    if not personagens:
        await interaction.response.send_message("Nenhum personagem criado.", ephemeral=True)
        return
    
    options = [discord.SelectOption(label=p.title(), value=p) for p in personagens]
    
    select = discord.ui.Select(
        placeholder="Escolha o personagem...",
        options=options,
        custom_id="status_personagem"
    )
    
    async def callback(interaction2: discord.Interaction):
        personagem = select.values[0]
        animo_max = bot.dados[personagem].get("animo_max", 3)
        animo_usados = bot.dados[personagem].get("animo_usados", 0)
        animo_disponivel = animo_max - animo_usados
        
        msg = f"**Status de {personagem.title()}**\n\n"
        msg += f"Animo: {animo_disponivel}/{animo_max}\n\n"
        
        for pilar in ["corpo", "mente", "alma"]:
            total, _ = calcular_penalidade_pilar(bot.dados[personagem], pilar)
            num_condicoes = len(bot.dados[personagem][pilar])
            if num_condicoes > 0:
                msg += f"**{pilar.title()}:** {num_condicoes} condicao(oes) | Penalidade: -{total}\n"
            else:
                msg += f"**{pilar.title()}:** Nenhuma condicao\n"
        
        await interaction2.response.send_message(msg)
    
    select.callback = callback
    view = discord.ui.View()
    view.add_item(select)
    
    await interaction.response.send_message("Escolha o personagem:", view=view, ephemeral=True)

# ============================================
# COMANDO: /limpar
# ============================================

@bot.tree.command(name="limpar", description="Remove todas as condicoes do personagem (mantem o personagem)")
async def limpar(interaction: discord.Interaction):
    personagens = list(bot.dados.keys())
    if not personagens:
        await interaction.response.send_message("Nenhum personagem criado.", ephemeral=True)
        return
    
    options = [discord.SelectOption(label=p.title(), value=p) for p in personagens]
    
    select = discord.ui.Select(
        placeholder="Escolha o personagem para limpar...",
        options=options,
        custom_id="limpar_personagem"
    )
    
    async def callback(interaction2: discord.Interaction):
        personagem = select.values[0]
        # Manter o personagem, so zerar as condicoes e animo
        bot.dados[personagem]["corpo"] = []
        bot.dados[personagem]["mente"] = []
        bot.dados[personagem]["alma"] = []
        bot.dados[personagem]["animo_usados"] = 0
        salvar_dados(bot.dados)
        await interaction2.response.send_message(f"Todas as condicoes de **{personagem.title()}** foram removidas. Personagem mantido.")
    
    select.callback = callback
    view = discord.ui.View()
    view.add_item(select)
    
    await interaction.response.send_message("Limpar personagem:", view=view, ephemeral=True)

# ============================================
# COMANDO: /excluir
# ============================================

@bot.tree.command(name="excluir", description="Exclui completamente um personagem")
async def excluir(interaction: discord.Interaction):
    personagens = list(bot.dados.keys())
    if not personagens:
        await interaction.response.send_message("Nenhum personagem criado.", ephemeral=True)
        return
    
    options = [discord.SelectOption(label=p.title(), value=p) for p in personagens]
    
    select = discord.ui.Select(
        placeholder="Escolha o personagem para excluir...",
        options=options,
        custom_id="excluir_personagem"
    )
    
    async def callback(interaction2: discord.Interaction):
        personagem = select.values[0]
        del bot.dados[personagem]
        salvar_dados(bot.dados)
        await interaction2.response.send_message(f"Personagem **{personagem.title()}** excluido permanentemente.")
    
    select.callback = callback
    view = discord.ui.View()
    view.add_item(select)
    
    await interaction.response.send_message("Excluir personagem:", view=view, ephemeral=True)

# ============================================
# INICIAR
# ============================================

keep_alive()
bot.run(TOKEN)
