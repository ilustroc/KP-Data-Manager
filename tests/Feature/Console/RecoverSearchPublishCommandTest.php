<?php

namespace Tests\Feature\Console;

use App\ImportStatus;
use Illuminate\Database\QueryException;
use Illuminate\Process\PendingProcess;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Process;
use Tests\Feature\Imports\ImportFeatureTestCase;

class RecoverSearchPublishCommandTest extends ImportFeatureTestCase
{
    protected function setUp(): void
    {
        parent::setUp();

        config([
            'etl.enabled' => true,
            'etl.python_binary' => PHP_BINARY,
            'etl.workdir' => base_path('etl'),
            'etl.process_timeout_seconds' => 3600,
        ]);
    }

    public function test_command_invokes_publish_only_worker_without_running_normal_import(): void
    {
        Process::fake([
            '*' => Process::result('{"event":"recovery_completed"}', exitCode: 0),
        ]);

        $this->artisan('imports:recover-search-publish', ['batch_id' => 39])
            ->expectsOutput('Publicación Gold recuperada correctamente.')
            ->assertSuccessful();

        Process::assertRan(fn (PendingProcess $process): bool => $process->command === [
            PHP_BINARY,
            '-m',
            'src.worker',
            '--batch-id',
            '39',
            '--publish-only',
        ]);
    }

    public function test_command_returns_safe_failure_when_publish_only_worker_fails(): void
    {
        $batchId = $this->createBatch(['estado' => ImportStatus::Processing->value]);
        Process::fake([
            '*' => Process::result(
                '{"event":"worker_crashed","stage":"search_gold_publish","error_type":"OperationalError","error_code":1205}',
                exitCode: 1,
            ),
        ]);

        $this->artisan('imports:recover-search-publish', ['batch_id' => $batchId])
            ->expectsOutput('No fue posible publicar Gold desde el batch SEARCH. Revisa el log técnico.')
            ->assertFailed();

        $batch = $this->batchRow($batchId);
        $this->assertSame(ImportStatus::Error->value, $batch->estado);
        $this->assertSame('No fue posible recuperar la publicación Gold SEARCH. Revisa el log técnico.', $batch->mensaje_error);
    }

    public function test_command_does_not_overwrite_existing_error_batch_after_failure(): void
    {
        $batchId = $this->createBatch([
            'estado' => ImportStatus::Error->value,
            'mensaje_error' => 'Error original seguro.',
        ]);
        Process::fake(['*' => Process::result('{"event":"worker_crashed"}', exitCode: 1)]);

        $this->artisan('imports:recover-search-publish', ['batch_id' => $batchId])->assertFailed();

        $batch = $this->batchRow($batchId);
        $this->assertSame(ImportStatus::Error->value, $batch->estado);
        $this->assertSame('Error original seguro.', $batch->mensaje_error);
    }

    public function test_command_does_not_overwrite_completed_batch_after_failure(): void
    {
        $batchId = $this->createBatch(['estado' => ImportStatus::Completed->value]);
        Process::fake(['*' => Process::result('{"event":"worker_crashed"}', exitCode: 1)]);

        $this->artisan('imports:recover-search-publish', ['batch_id' => $batchId])->assertFailed();

        $this->assertSame(ImportStatus::Completed->value, $this->batchRow($batchId)->estado);
    }

    public function test_command_handles_fallback_database_failure_without_exposing_query_details(): void
    {
        Log::spy();
        $batchId = $this->createBatch(['estado' => ImportStatus::Processing->value]);
        config(['imports.table' => 'missing_import_batch']);
        Process::fake(['*' => Process::result('{"event":"worker_crashed"}', exitCode: 1)]);

        $this->artisan('imports:recover-search-publish', ['batch_id' => $batchId])
            ->expectsOutput('No fue posible publicar Gold desde el batch SEARCH. El estado del batch no pudo actualizarse automáticamente. Revisa el log técnico.')
            ->assertFailed();

        Log::shouldHaveReceived('error')->once()->withArgs(function (string $message, array $context): bool {
            $serializedContext = json_encode($context, JSON_THROW_ON_ERROR);

            return $message === 'No fue posible marcar ERROR después de un fallo de recuperación SEARCH.'
                && $context['fallback_mark_error_failed'] === true
                && $context['exception_class'] === QueryException::class
                && ! str_contains($serializedContext, 'missing_import_batch')
                && ! str_contains($serializedContext, 'SQL')
                && ! str_contains($serializedContext, 'host')
                && ! str_contains($serializedContext, 'port')
                && ! str_contains($serializedContext, 'database');
        });
    }
}
