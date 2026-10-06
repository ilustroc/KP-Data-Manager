<?php

namespace Tests\Feature\Imports;

use App\ImportStatus;
use App\Jobs\ProcessImportBatch;
use App\Models\User;
use App\UserRole;
use Illuminate\Support\Facades\Queue;
use PHPUnit\Framework\Attributes\DataProvider;

class ImportProcessControllerTest extends ImportFeatureTestCase
{
    public function test_unauthenticated_user_cannot_request_processing(): void
    {
        Queue::fake([ProcessImportBatch::class]);
        $batchId = $this->createBatch();

        $this->post(route('imports.process', $batchId))->assertRedirectToRoute('login');

        Queue::assertNothingPushed();
    }

    public function test_read_only_user_cannot_request_processing(): void
    {
        Queue::fake([ProcessImportBatch::class]);
        $batchId = $this->createBatch();
        $user = User::factory()->readOnly()->create();

        $this->actingAs($user)->post(route('imports.process', $batchId))->assertForbidden();

        Queue::assertNothingPushed();
    }

    #[DataProvider('operatorRoles')]
    public function test_operator_role_can_enqueue_pending_batch(UserRole $role): void
    {
        Queue::fake([ProcessImportBatch::class]);
        $batchId = $this->createBatch();
        $user = User::factory()->create(['role' => $role]);

        $this->actingAs($user)
            ->post(route('imports.process', $batchId))
            ->assertRedirectToRoute('imports.show', $batchId)
            ->assertSessionHas('status', 'El procesamiento fue enviado a la cola.');

        Queue::assertPushed(ProcessImportBatch::class, function (ProcessImportBatch $job) use ($batchId): bool {
            return $job->batchId === $batchId && $job->queue === 'etl';
        });
    }

    public function test_unknown_batch_returns_404_without_enqueuing(): void
    {
        Queue::fake([ProcessImportBatch::class]);
        $user = User::factory()->operator()->create();

        $this->actingAs($user)->post(route('imports.process', 999999))->assertNotFound();

        Queue::assertNothingPushed();
    }

    #[DataProvider('nonPendingStatuses')]
    public function test_non_pending_batch_returns_422_without_enqueuing(ImportStatus $status): void
    {
        Queue::fake([ProcessImportBatch::class]);
        $batchId = $this->createBatch(['estado' => $status->value]);
        $user = User::factory()->operator()->create();

        $this->actingAs($user)
            ->post(route('imports.process', $batchId))
            ->assertUnprocessable();

        Queue::assertNothingPushed();
    }

    public function test_double_request_enqueues_only_one_unique_job(): void
    {
        Queue::fake([ProcessImportBatch::class]);
        $batchId = $this->createBatch();
        $user = User::factory()->operator()->create();

        $this->actingAs($user)->post(route('imports.process', $batchId))->assertRedirect();
        $this->actingAs($user)->post(route('imports.process', $batchId))->assertRedirect();

        Queue::assertPushed(ProcessImportBatch::class, 1);
    }

    public function test_read_only_user_can_view_status_without_process_button(): void
    {
        $batchId = $this->createBatch();
        $user = User::factory()->readOnly()->create();

        $this->actingAs($user)
            ->get(route('imports.show', $batchId))
            ->assertSeeText('Preparando procesamiento...')
            ->assertSee('data-auto-refresh-after="8000"', false)
            ->assertDontSeeText('Procesar carga');
    }

    public function test_processing_detail_shows_real_processed_rows_and_manual_refresh(): void
    {
        $batchId = $this->createBatch([
            'estado' => ImportStatus::Processing->value,
            'filas_archivo' => 5000,
        ]);
        $user = User::factory()->readOnly()->create();

        $this->actingAs($user)
            ->get(route('imports.show', $batchId))
            ->assertSeeText('Procesando carga')
            ->assertSeeText('La información está siendo validada y cargada.')
            ->assertSeeText('5,000')
            ->assertSeeText('Actualizar estado')
            ->assertDontSee('%');
    }

    public function test_detail_uses_simplified_user_facing_language_and_hides_technical_metadata(): void
    {
        $batchId = $this->createBatch([
            'archivo_original' => 'pagos subir.xlsx',
            'archivo_tamano' => 36096,
            'archivo_extension' => 'xlsx',
            'archivo_mime' => 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'archivo_sha256' => str_repeat('a', 64),
            'filas_archivo' => 73,
            'filas_insertadas' => 72,
            'filas_duplicadas' => 8,
            'filas_error' => 1,
        ]);
        $user = User::factory()->operator()->create();

        $this->actingAs($user)
            ->get(route('imports.show', $batchId))
            ->assertOk()
            ->assertSeeText("Carga #{$batchId}")
            ->assertSeeText('pagos subir.xlsx')
            ->assertSeeText('35.25 KB')
            ->assertSee('assets/brand/kp-invest-logo.png', false)
            ->assertSee('assets/brand/kp-invest-mark.png', false)
            ->assertSeeText('Filas del archivo')
            ->assertSeeText('Cargadas')
            ->assertSeeText('Con error')
            ->assertDontSeeText('Batch')
            ->assertDontSeeText('SHA-256')
            ->assertDontSeeText('MIME')
            ->assertDontSeeText('Extensión')
            ->assertDontSeeText('Duplicadas')
            ->assertDontSeeText('Procesar carga');
    }

    public function test_etl_environment_file_is_not_web_accessible(): void
    {
        $this->get('/etl/.env')->assertNotFound();
    }

    /**
     * @return array<string, array{UserRole}>
     */
    public static function operatorRoles(): array
    {
        return [
            'administrador' => [UserRole::Admin],
            'operador' => [UserRole::Operator],
        ];
    }

    /**
     * @return array<string, array{ImportStatus}>
     */
    public static function nonPendingStatuses(): array
    {
        return [
            'recibido' => [ImportStatus::Received],
            'validando' => [ImportStatus::Validating],
            'procesando' => [ImportStatus::Processing],
            'completado' => [ImportStatus::Completed],
            'completado con errores' => [ImportStatus::CompletedWithErrors],
            'error' => [ImportStatus::Error],
            'cancelado' => [ImportStatus::Cancelled],
        ];
    }
}
