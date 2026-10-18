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

    public function test_runner_persists_all_search_phase_metrics_after_process_exit(): void
    {
        Log::spy();
        $phaseMetric = $this->searchMetric([
            'batch_id' => 999,
            'phase' => 'gold_insert',
            'duration_seconds' => 2.5,
            'rows_processed' => 41040,
            'rows_per_second' => 16416.0,
            'logical_statement_count' => 1,
            'physical_statement_count' => 1,
            'documento' => '09529768',
            'sql' => 'DELETE FROM sensitive_table',
            'bindings' => ['sensitive'],
        ]);
        $totalMetric = $this->searchMetric([
            'batch_id' => 999,
            'phase' => 'total',
            'duration_seconds' => 9.75,
            'rows_processed' => 41040,
            'rows_per_second' => 4209.231,
            'logical_statement_count' => 16,
            'physical_statement_count' => 15,
            'invocations' => 15,
            'last_phase' => 'commit',
        ]);
        Process::fake([
            '*' => Process::result(
                $phaseMetric."\n".$totalMetric."\n".'{"event":"worker_completed"}',
                exitCode: 0,
            ),
        ]);

        $result = (new EtlProcessRunner)->run(123);

        $this->assertSame('worker_completed', $result->lastEvent);
        $loggedMetrics = [];
        Log::shouldHaveReceived('info')->twice()->withArgs(
            function (string $message, array $context) use (&$loggedMetrics): bool {
                $loggedMetrics[$context['phase']] = $context;

                return $message === 'search_phase_metric';
            },
        );
        $this->assertSame([
            'batch_id' => 123,
            'dataset_code' => 'FAMILIA',
            'refresh_mode' => 'FULL_REPLACE',
            'phase' => 'gold_insert',
            'duration_seconds' => 2.5,
            'rows_processed' => 41040,
            'rows_per_second' => 16416.0,
            'logical_statement_count' => 1,
            'executemany_calls' => 0,
            'physical_statement_count' => 1,
            'invocations' => 1,
            'peak_memory_mb' => null,
            'successful' => true,
            'last_phase' => null,
            'failed_phase' => null,
        ], $loggedMetrics['gold_insert']);
        $this->assertSame([
            'batch_id' => 123,
            'dataset_code' => 'FAMILIA',
            'refresh_mode' => 'FULL_REPLACE',
            'phase' => 'total',
            'duration_seconds' => 9.75,
            'rows_processed' => 41040,
            'rows_per_second' => 4209.231,
            'logical_statement_count' => 16,
            'executemany_calls' => 0,
            'physical_statement_count' => 15,
            'invocations' => 15,
            'peak_memory_mb' => null,
            'successful' => true,
            'last_phase' => 'commit',
            'failed_phase' => null,
        ], $loggedMetrics['total']);
    }

    public function test_runner_persists_failed_metric_without_free_form_sensitive_fields(): void
    {
        Log::spy();
        $metric = $this->searchMetric([
            'phase' => 'gold_insert',
            'successful' => false,
            'last_phase' => 'gold_insert',
            'failed_phase' => 'gold_insert',
            'documento' => '09529768',
            'nombre' => 'Sensitive Name',
            'raw_payload' => ['sensitive'],
            'password' => 'secret',
        ]);
        Process::fake([
            '*' => Process::result(
                $metric."\n".'{"event":"worker_crashed","stage":"search_gold_publish","error_type":"OperationalError","error_code":2013,"db_driver":"pymysql","connection_phase":"execute","retryable":true}',
                exitCode: 1,
            ),
        ]);

        (new EtlProcessRunner)->run(456);

        Log::shouldHaveReceived('info')->once()->withArgs(
            function (string $message, array $context): bool {
                $serialized = json_encode($context, JSON_THROW_ON_ERROR);

                return $message === 'search_phase_metric'
                    && $context['batch_id'] === 456
                    && $context['phase'] === 'gold_insert'
                    && $context['successful'] === false
                    && $context['failed_phase'] === 'gold_insert'
                    && ! str_contains($serialized, '09529768')
                    && ! str_contains($serialized, 'Sensitive Name')
                    && ! str_contains($serialized, 'secret');
            },
        );
    }

    public function test_runner_ignores_malformed_or_unknown_search_metrics(): void
    {
        Log::spy();
        Process::fake([
            '*' => Process::result(
                $this->searchMetric(['phase' => 'unknown_phase'])."\n".'{"event":"worker_completed"}',
                exitCode: 0,
            ),
        ]);

        (new EtlProcessRunner)->run(123);

        Log::shouldNotHaveReceived('info');
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

    /**
     * @param  array<string, mixed>  $overrides
     */
    private function searchMetric(array $overrides = []): string
    {
        return json_encode(array_replace([
            'event' => 'search_phase_metric',
            'batch_id' => 42,
            'dataset_code' => 'FAMILIA',
            'refresh_mode' => 'FULL_REPLACE',
            'phase' => 'parse_normalize',
            'duration_seconds' => 0.5,
            'rows_processed' => 100,
            'rows_per_second' => 200.0,
            'logical_statement_count' => 0,
            'executemany_calls' => 0,
            'physical_statement_count' => 0,
            'invocations' => 1,
            'peak_memory_mb' => null,
            'successful' => true,
            'last_phase' => null,
            'failed_phase' => null,
        ], $overrides), JSON_THROW_ON_ERROR);
    }
}
