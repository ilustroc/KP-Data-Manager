<?php

namespace Tests\Feature\Imports;

use App\ImportStatus;
use App\Jobs\ProcessImportBatch;
use App\Services\Imports\EtlProcessFailed;
use App\Services\Imports\EtlProcessStartFailed;
use Illuminate\Contracts\Queue\ShouldBeUnique;
use Illuminate\Process\PendingProcess;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Process;

class ProcessImportBatchTest extends ImportFeatureTestCase
{
    protected function setUp(): void
    {
        parent::setUp();

        config([
            'etl.enabled' => true,
            'etl.python_binary' => PHP_BINARY,
            'etl.workdir' => base_path('etl'),
            'etl.process_timeout_seconds' => 3600,
            'etl.queue' => 'etl',
        ]);
    }

    public function test_job_is_unique_per_batch_and_has_no_automatic_retry(): void
    {
        $job = new ProcessImportBatch(27);

        $this->assertInstanceOf(ShouldBeUnique::class, $job);
        $this->assertSame('27', $job->uniqueId());
        $this->assertSame(1, $job->tries);
        $this->assertSame(3600, $job->timeout);
        $this->assertTrue($job->failOnTimeout);
        $this->assertSame('etl', $job->queue);
    }

    public function test_job_revalidates_pending_state_before_running_process(): void
    {
        Process::fake();
        $batchId = $this->createBatch(['estado' => ImportStatus::Completed->value]);

        app()->call([new ProcessImportBatch($batchId), 'handle']);

        Process::assertNothingRan();
        $this->assertSame(ImportStatus::Completed->value, $this->batchRow($batchId)->estado);
    }

    public function test_successful_process_exit_is_accepted(): void
    {
        Process::fake([
            '*' => Process::result('{"event":"worker_completed"}', exitCode: 0),
        ]);
        $batchId = $this->createBatch();

        app()->call([new ProcessImportBatch($batchId), 'handle']);

        Process::assertRan(fn (PendingProcess $process): bool => $process->command[4] === (string) $batchId);
    }

    public function test_nonzero_exit_fails_job_without_overwriting_python_status(): void
    {
        $batchId = $this->createBatch();
        Process::fake(function () use ($batchId) {
            DB::connection('sqlite')->table('import_batch')->where('batch_id', $batchId)->update([
                'estado' => ImportStatus::Error->value,
                'mensaje_error' => 'Error seguro escrito por Python.',
            ]);

            return Process::result('{"event":"worker_rejected"}', exitCode: 1);
        });

        try {
            app()->call([new ProcessImportBatch($batchId), 'handle']);
            $this->fail('El Job debía fallar con exit code distinto de cero.');
        } catch (EtlProcessFailed $exception) {
            $this->assertSame('El procesador ETL finalizó con error.', $exception->getMessage());
        }

        $batch = $this->batchRow($batchId);
        $this->assertSame(ImportStatus::Error->value, $batch->estado);
        $this->assertSame('Error seguro escrito por Python.', $batch->mensaje_error);
    }

    public function test_start_failure_marks_pending_batch_error_with_safe_message(): void
    {
        Process::fake();
        config(['etl.python_binary' => base_path('missing-python.exe')]);
        $batchId = $this->createBatch();

        try {
            app()->call([new ProcessImportBatch($batchId), 'handle']);
            $this->fail('El Job debía fallar al no encontrar el binario.');
        } catch (EtlProcessStartFailed $exception) {
            $this->assertSame('No fue posible iniciar el procesador ETL.', $exception->getMessage());
        }

        Process::assertNothingRan();
        $batch = $this->batchRow($batchId);
        $this->assertSame(ImportStatus::Error->value, $batch->estado);
        $this->assertSame('No fue posible iniciar el procesamiento.', $batch->mensaje_error);
    }
}
