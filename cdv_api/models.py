from django.db import models
from django.utils import timezone


# Definindo as opções para o tipo de manutenção
TIPO_MANUTENCAO_CHOICES = [
    ('preventiva', 'Preventiva'),
    ('corretiva', 'Corretiva'),
    ('checklist', 'Checklist'),
] 

class Estacao(models.Model):
    nome = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nome

class Transmissor(models.Model):
    estacao = models.ForeignKey(Estacao, on_delete=models.CASCADE, related_name='transmissores')
    num_circuito = models.CharField(max_length=50)
    num_transmissor = models.CharField(max_length=50)
    vout = models.FloatField(null=True, blank=True)
    pout = models.FloatField(null=True, blank=True)
    tap = models.CharField(max_length=20, blank=True)
    tipo_transmissor = models.CharField(max_length=50, blank=True)
    data_manutencao = models.DateTimeField(default=timezone.now)    
    horario_coleta = models.TimeField(null=True, blank=True)
    temp_celsius = models.FloatField(null=True, blank=True)
    tipo_manutencao = models.CharField(max_length=20, choices=TIPO_MANUTENCAO_CHOICES)

    def __str__(self):
        return f"Transmissor {self.num_transmissor} (Circuito {self.num_circuito}) da Estação {self.estacao.nome}"


class Receptor(models.Model):
    estacao = models.ForeignKey(Estacao, on_delete=models.CASCADE, related_name='receptores')
    num_circuito = models.CharField(max_length=50)
    num_receptor = models.CharField(max_length=50)
    iav = models.FloatField(null=True, blank=True)
    ith = models.FloatField(null=True, blank=True)
    relacao = models.CharField(max_length=100, blank=True, null=True)
    data_manutencao = models.DateTimeField(default=timezone.now)
    horario_coleta = models.TimeField(null=True, blank=True)
    temp_celsius = models.FloatField(null=True, blank=True)
    tipo_manutencao = models.CharField(max_length=20, choices=TIPO_MANUTENCAO_CHOICES)

    def __str__(self):
        return f"Receptor {self.num_receptor} (Circuito {self.num_circuito}) da Estação {self.estacao.nome}"


from django.db import models

class BaselineCDV(models.Model):
    estacao = models.ForeignKey("Estacao", on_delete=models.CASCADE, related_name="baselines")
    num_circuito = models.CharField(max_length=50)

    # Referência TX
    vout_ref = models.FloatField(null=True, blank=True, verbose_name="VOUT de referência")
    pout_ref = models.FloatField(null=True, blank=True, verbose_name="POUT de referência")
    tap_ref = models.IntegerField(null=True, blank=True, verbose_name="TAP de referência")
    tipo_tx_ref = models.CharField(max_length=50, null=True, blank=True, verbose_name="Tipo TX de referência")

    # Referência RX
    iav_ref = models.FloatField(null=True, blank=True, verbose_name="IAV de referência")
    ith_ref = models.FloatField(null=True, blank=True, verbose_name="ITH de referência")
    relacao_ref = models.FloatField(null=True, blank=True, verbose_name="Relação de referência")

    # Metadados do comissionamento
    data_comissionamento = models.DateField(verbose_name="Data do comissionamento")
    observacoes = models.TextField(blank=True, null=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Baseline CDV"
        verbose_name_plural = "Baselines CDV"
        ordering = ["estacao__nome", "num_circuito"]
        constraints = [
            models.UniqueConstraint(
                fields=["estacao", "num_circuito"],
                name="unique_baseline_por_estacao_circuito"
            )
        ]

    def __str__(self):
        return f"{self.estacao.nome} - {self.num_circuito}"