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
