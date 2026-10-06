<?php

namespace Tests\Unit\Services\Imports;

use App\Services\Imports\EtlProcessRunner;
use App\Services\Imports\EtlProcessStartFailed;
use Illuminate\Process\PendingProcess;
use Illuminate\Support\Facades\Process;
use Tests\TestCase;

class EtlProcessRunnerTest extends TestCase
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

    public function test_runner_uses_configured_binary_workdir_and_separate_arguments(): void
    {
        Process::fake([
            '*' => Process::result(
                "{\"event\":\"batch_started\"}\n{\"event\":\"worker_completed\"}\n",
                exitCode: 0,
            ),
        ]);

        $result = (new EtlProcessRunner)->run(123);

        $this->assertTrue($result->successful());
        $this->assertSame(0, $result->exitCode);
        $this->assertSame('worker_completed', $result->lastEvent);
        Process::assertRan(function (PendingProcess $process): bool {
            return $process->command === [
                PHP_BINARY,
                '-m',
                'src.worker',
                '--batch-id',
                '123',
            ]
                && $process->path === base_path('etl')
                && $process->timeout === 3600
                && $process->environment === [];
        });
    }

    public function test_runner_returns_nonzero_exit_without_exposing_output(): void
    {
        Process::fake([
            '*' => Process::result(
                '{"event":"worker_crashed","exception":"traceback with ETL_DB_PASSWORD=secret"}',
                errorOutput: 'sensitive stderr',
                exitCode: 1,
            ),
        ]);

        $result = (new EtlProcessRunner)->run(456);

        $this->assertFalse($result->successful());
        $this->assertSame(1, $result->exitCode);
        $this->assertSame('worker_crashed', $result->lastEvent);
    }

    public function test_missing_binary_is_rejected_before_process_execution(): void
    {
        Process::fake();
        config(['etl.python_binary' => base_path('missing-python')]);

        try {
            (new EtlProcessRunner)->run(123);
            $this->fail('El runner debía rechazar un binario inexistente.');
        } catch (EtlProcessStartFailed $exception) {
            $this->assertSame('No fue posible iniciar el procesador ETL.', $exception->getMessage());
        }

        Process::assertNothingRan();
    }

    public function test_missing_workdir_is_rejected_before_process_execution(): void
    {
        Process::fake();
        config(['etl.workdir' => base_path('missing-etl-workdir')]);

        try {
            (new EtlProcessRunner)->run(123);
            $this->fail('El runner debía rechazar un directorio inexistente.');
        } catch (EtlProcessStartFailed $exception) {
            $this->assertSame('No fue posible iniciar el procesador ETL.', $exception->getMessage());
        }

        Process::assertNothingRan();
    }

    public function test_zero_timeout_runs_without_process_timeout(): void
    {
        Process::fake();
        config(['etl.process_timeout_seconds' => 0]);

        (new EtlProcessRunner)->run(123);

        Process::assertRan(fn (PendingProcess $process): bool => $process->timeout === null);
    }

    public function test_runner_does_not_pass_database_password_or_env_file(): void
    {
        Process::fake();
        config(['etl.database_password' => 'not-a-real-secret']);

        (new EtlProcessRunner)->run(123);

        Process::assertRan(function (PendingProcess $process): bool {
            $serializedCommand = implode(' ', $process->command);

            return $process->environment === []
                && ! str_contains($serializedCommand, 'not-a-real-secret')
                && ! str_contains($serializedCommand, '.env');
        });
    }

    public function test_disabled_integration_does_not_start_process(): void
    {
        Process::fake();
        config(['etl.enabled' => false]);

        $this->expectException(EtlProcessStartFailed::class);

        try {
            (new EtlProcessRunner)->run(123);
        } finally {
            Process::assertNothingRan();
        }
    }
}
