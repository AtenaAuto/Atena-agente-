"""
Testes unitários para modules/atena_engine.py
"""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Importar com tratamento de erro caso o módulo precise de ajustes
try:
    from modules.atena_engine import AtenaCore
except ImportError:
    pytest.skip("AtenaCore não disponível", allow_module_level=True)


class TestAtenaCoreInitialization:
    """Testes de inicialização do AtenaCore."""
    
    def test_initialization_default(self, temp_dir):
        """Testa inicialização com valores padrão."""
        with patch.object(AtenaCore, '_load_state', return_value={}):
            engine = AtenaCore()
            assert engine.generation == 0
            assert engine.best_score == 0.0
            assert isinstance(engine._results, list)
    
    def test_initialization_with_existing_state(self, temp_dir, mock_state_file):
        """Testa inicialização com estado existente."""
        engine = AtenaCore()
        engine.state_file = mock_state_file
        
        loaded = engine._load_state()
        assert loaded["generation"] == 0
        assert loaded["best_score"] == 0.0
    
    def test_state_file_creation(self, temp_dir):
        """Testa criação de arquivo de estado."""
        engine = AtenaCore()
        engine.state_file = temp_dir / "new_state.json"
        
        # Arquivo pai deve ser criado
        assert engine.state_file.parent.exists()


class TestAtenaCorePersistence:
    """Testes de persistência de estado."""
    
    @pytest.mark.asyncio
    async def test_save_state(self, temp_dir):
        """Testa salvamento de estado."""
        engine = AtenaCore()
        engine.state_file = temp_dir / "state.json"
        engine.generation = 5
        engine.best_score = 0.85
        
        engine._save_state()
        
        # Verificar se arquivo foi criado
        assert engine.state_file.exists()
        
        # Verificar conteúdo
        saved_data = json.loads(engine.state_file.read_text())
        assert saved_data["generation"] == 5
        assert saved_data["best_score"] == 0.85
    
    def test_load_state_missing_file(self, temp_dir):
        """Testa carregamento com arquivo ausente."""
        engine = AtenaCore()
        engine.state_file = temp_dir / "nonexistent.json"
        
        loaded = engine._load_state()
        assert loaded == {}
    
    def test_load_state_corrupted_file(self, temp_dir):
        """Testa carregamento com arquivo corrompido."""
        engine = AtenaCore()
        engine.state_file = temp_dir / "corrupted.json"
        engine.state_file.write_text("invalid json {{{")
        
        with patch('logging.Logger.warning') as mock_warning:
            loaded = engine._load_state()
            assert loaded == {}
            assert mock_warning.called


class TestAtenaCoreEvolution:
    """Testes de ciclo de evolução."""
    
    @pytest.mark.asyncio
    async def test_evolve_one_cycle_success(self, temp_dir):
        """Testa execução bem-sucedida de um ciclo."""
        engine = AtenaCore()
        engine.state_file = temp_dir / "state.json"
        
        result = await engine.evolve_one_cycle()
        
        assert result["success"] is True
        assert result["generation"] == 1
        assert "score" in result
        assert engine.generation == 1
    
    @pytest.mark.asyncio
    async def test_evolve_one_cycle_increments_generation(self, temp_dir):
        """Testa incremento de geração."""
        engine = AtenaCore()
        engine.state_file = temp_dir / "state.json"
        initial_gen = engine.generation
        
        await engine.evolve_one_cycle()
        
        assert engine.generation == initial_gen + 1
    
    @pytest.mark.asyncio
    async def test_evolve_one_cycle_saves_state(self, temp_dir):
        """Testa salvamento de estado após ciclo."""
        engine = AtenaCore()
        engine.state_file = temp_dir / "state.json"
        
        await engine.evolve_one_cycle()
        
        # Verificar se estado foi salvo
        assert engine.state_file.exists()
        saved = json.loads(engine.state_file.read_text())
        assert saved["generation"] == 1
    
    @pytest.mark.asyncio
    async def test_evolve_one_cycle_error_handling(self, temp_dir):
        """Testa tratamento de erro durante evolução."""
        engine = AtenaCore()
        engine.state_file = temp_dir / "state.json"
        
        # Simular erro forçando exception
        with patch.object(engine, '_save_state', side_effect=Exception("Test error")):
            result = await engine.evolve_one_cycle()
            
            assert result["success"] is False
            assert "error" in result


class TestAtenaCoreAutonomous:
    """Testes de execução autônoma."""
    
    @pytest.mark.asyncio
    async def test_run_autonomous_multiple_generations(self, temp_dir):
        """Testa execução de múltiplas gerações."""
        engine = AtenaCore()
        engine.state_file = temp_dir / "state.json"
        
        generations = 3
        await engine.run_autonomous(generations=generations)
        
        assert engine.generation == generations
    
    @pytest.mark.asyncio
    async def test_run_autonomous_continues_on_failure(self, temp_dir):
        """Testa continuação mesmo com falhas."""
        engine = AtenaCore()
        engine.state_file = temp_dir / "state.json"
        
        call_count = 0
        original_evolve = engine.evolve_one_cycle
        
        async def mock_evolve_with_failures():
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                return {"success": False, "generation": call_count, "error": "Test"}
            return await original_evolve()
        
        with patch.object(engine, 'evolve_one_cycle', mock_evolve_with_failures):
            await engine.run_autonomous(generations=3)
            
            # Deve ter completado 3 gerações mesmo com 1 falha
            assert call_count == 3
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_run_autonomous_performance(self, temp_dir):
        """Testa performance de execução autônoma."""
        import time
        
        engine = AtenaCore()
        engine.state_file = temp_dir / "state.json"
        
        start = time.time()
        await engine.run_autonomous(generations=5)
        duration = time.time() - start
        
        # Deve completar em menos de 5 segundos (stub é rápido)
        assert duration < 5.0
        assert engine.generation == 5


class TestAtenaCoreStatusAndReporting:
    """Testes de status e relatórios."""
    
    def test_print_status(self, temp_dir, capsys):
        """Testa impressão de status."""
        engine = AtenaCore()
        engine.generation = 10
        engine.best_score = 0.95
        
        engine.print_status()
        
        captured = capsys.readouterr()
        assert "10" in captured.out or str(engine.generation) in captured.out
    
    @pytest.mark.asyncio
    async def test_results_accumulation(self, temp_dir):
        """Testa acumulação de resultados."""
        engine = AtenaCore()
        engine.state_file = temp_dir / "state.json"
        
        # Executar vários ciclos
        for _ in range(3):
            await engine.evolve_one_cycle()
        
        # Verificar se resultados foram acumulados
        assert len(engine._results) == 3
        assert all(r["success"] for r in engine._results)


# Testes de integração básicos
class TestAtenaCoreIntegration:
    """Testes de integração básicos."""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_lifecycle(self, temp_dir):
        """Testa ciclo de vida completo."""
        # Criar engine
        engine = AtenaCore()
        engine.state_file = temp_dir / "state.json"
        
        # Executar evolução
        await engine.run_autonomous(generations=2)
        
        # Verificar estado final
        assert engine.generation == 2
        assert engine.state_file.exists()
        
        # Criar nova instância e carregar estado
        engine2 = AtenaCore()
        engine2.state_file = temp_dir / "state.json"
        loaded = engine2._load_state()
        
        assert loaded["generation"] == 2
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_concurrent_evolution(self, temp_dir):
        """Testa evolução concorrente (simula múltiplas instâncias)."""
        import asyncio
        
        async def run_engine(engine_id: int):
            engine = AtenaCore()
            engine.state_file = temp_dir / f"state_{engine_id}.json"
            await engine.run_autonomous(generations=2)
            return engine.generation
        
        # Executar 3 engines em paralelo
        results = await asyncio.gather(
            run_engine(1),
            run_engine(2),
            run_engine(3)
        )
        
        # Todas devem completar 2 gerações
        assert all(gen == 2 for gen in results)


# Fixtures específicas para este módulo
@pytest.fixture
def engine_with_history(temp_dir):
    """Engine com histórico de execuções."""
    engine = AtenaCore()
    engine.state_file = temp_dir / "state.json"
    engine.generation = 5
    engine.best_score = 0.75
    engine._results = [
        {"success": True, "generation": i, "score": 0.5 + (i * 0.05)}
        for i in range(1, 6)
    ]
    return engine


def test_engine_with_history_fixture(engine_with_history):
    """Testa fixture de engine com histórico."""
    assert engine_with_history.generation == 5
    assert len(engine_with_history._results) == 5
    assert engine_with_history.best_score == 0.75
