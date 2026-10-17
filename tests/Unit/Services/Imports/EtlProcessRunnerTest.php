<?php

namespace Tests\Unit\Services\Imports;

use App\Services\Imports\EtlProcessRunner;
use App\Services\Imports\EtlProcessStartFailed;
use Illuminate\Process\PendingProcess;
use Illuminate\Support\Facades\Log;
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
        $this->assertNull($result->stage);
        $this->assertFalse($result->stderrPresent);
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
        Log::spy();
        Process::fake([
            '*' => Process::result(
                '{"event":"worker_crashed","stage":"search_gold_publish","error_type":"InterfaceError","error_code":0,"db_driver":"pymysql","connection_phase":"execute","retryable":true,"exception":"traceback with ETL_DB_PASSWORD=secret"}',
                errorOutput: 'sensitive stderr',
                exitCode: 1,
            ),
        ]);

        $result = (new EtlProcessRunner)->run(456);

        $this->assertFalse($result->successful());
        $this->assertSame(1, $result->exitCode);
        $this->assertSame('worker_crashed', $result->lastEvent);
        $this->assertSame('search_gold_publish', $result->stage);
        $this->assertSame('InterfaceError', $result->errorType);
        $this->assertSame(0, $result->errorCode);
        $this->assertSame('pymysql', $result->dbDriver);
        $this->assertSame('execute', $result->connectionPhase);
        $this->assertTrue($result->retryable);
        $this->assertTrue($result->stderrPresent);
        Log::shouldHaveReceived('warning')->once()->withArgs(function (string $message, array $context): bool {
            return $message === 'El proceso ETL finalizó con diagnóstico controlado.'
                && ! str_contains(json_encode($context, JSON_THROW_ON_ERROR), 'ETL_DB_PASSWORD');
        });
    }

    public function test_runner_adds_publish_only_without_database_credentials(): void
    {
        Process::fake([
            '*' => Process::result('{"event":"recovery_completed"}', exitCode: 0),
        ]);

        (new EtlProcessRunner)->runPublishOnly(789);

        Process::assertRan(fn (PendingProcess $process): bool => $process->command === [
            PHP_BINARY,
            '-m',
            'src.worker',
            '--batch-id',
            '789',
            '--publish-only',
        ] && $process->environment === []);
    }

    public function test_runner_uses_only_allowlisted_diagnostic_fields_from_stderr_when_stdout_has_none(): void
    {
        Process::fake([
            '*' => Process::result(
                'non-json worker output',
                errorOutput: '{"event":"worker_crashed","stage":"search_gold_publish","error_type":"OperationalError","error_code":1205,"message":"password=secret"}',
                exitCode: 1,
            ),
        ]);

        $result = (new EtlProcessRunner)->run(456);

        $this->assertSame('worker_crashed', $result->lastEvent);
        $this->assertSame('search_gold_publish', $result->stage);
        $this->assertSame('OperationalError', $result->errorType);
        $this->assertSame(1205, $result->errorCode);
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
