<?php

namespace Tests\Feature\Imports;

use App\ImportOrigin;
use App\ImportStatus;
use App\ImportType;
use App\Models\User;
use App\Services\Imports\ImportFileService;
use Illuminate\Database\Events\QueryExecuted;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;
use Mockery\MockInterface;
use PHPUnit\Framework\Attributes\DataProvider;

class ImportDeletionControllerTest extends ImportFeatureTestCase
{
    protected function setUp(): void
    {
        parent::setUp();

        Storage::fake('imports');
    }

    public function test_admin_sees_delete_action_for_eligible_historical_portfolio(): void
    {
        $admin = User::factory()->admin()->create();
        $batchId = $this->createDeletableBatch('COMPARTAMOS');

        $this->actingAs($admin)
            ->get(route('imports.show', $batchId))
            ->assertOk()
            ->assertSeeText('Eliminar carga')
            ->assertSeeText("Eliminar carga #{$batchId}")
            ->assertSee('ELIMINAR');
    }

    #[DataProvider('nonAdminUsers')]
    public function test_non_admin_does_not_see_delete_action(string $factoryState): void
    {
        $user = User::factory()->{$factoryState}()->create();
        $batchId = $this->createDeletableBatch('COMPARTAMOS');

        $this->actingAs($user)
            ->get(route('imports.show', $batchId))
            ->assertOk()
            ->assertDontSeeText('Eliminar carga');
    }

    #[DataProvider('nonAdminUsers')]
    public function test_non_admin_receives_forbidden_when_calling_delete_route(string $factoryState): void
    {
        $user = User::factory()->{$factoryState}()->create();
        $batchId = $this->createDeletableBatch('COMPARTAMOS');

        $this->actingAs($user)
            ->delete(route('imports.destroy', $batchId), ['confirmation' => 'ELIMINAR'])
            ->assertForbidden();

        $this->assertDatabaseHas('import_batch', ['batch_id' => $batchId]);
    }

    public function test_confirmation_must_match_eliminar_exactly(): void
    {
        $admin = User::factory()->admin()->create();
        $batchId = $this->createDeletableBatch('COMPARTAMOS');

        $this->actingAs($admin)
            ->from(route('imports.show', $batchId))
            ->delete(route('imports.destroy', $batchId), ['confirmation' => 'eliminar'])
            ->assertRedirect(route('imports.show', $batchId))
            ->assertSessionHasErrors('confirmation');

        $this->assertDatabaseHas('import_batch', ['batch_id' => $batchId]);
    }

    public function test_payments_cannot_be_deleted(): void
    {
        $admin = User::factory()->admin()->create();
        $batchId = $this->createBatch([
            'tipo' => ImportType::Payments->value,
            'origen' => ImportOrigin::Historical->value,
            'estado' => ImportStatus::Completed->value,
        ]);

        $this->actingAs($admin)
            ->delete(route('imports.destroy', $batchId), ['confirmation' => 'ELIMINAR'])
            ->assertSessionHas('warning', 'Solo se pueden eliminar cargas históricas de cartera.');

        $this->assertDatabaseHas('import_batch', ['batch_id' => $batchId]);
    }

    public function test_non_historical_portfolio_cannot_be_deleted(): void
    {
        $admin = User::factory()->admin()->create();
        $batchId = $this->createDeletableBatch('BBVA', [
            'origen' => ImportOrigin::Daily->value,
        ]);

        $this->actingAs($admin)
            ->delete(route('imports.destroy', $batchId), ['confirmation' => 'ELIMINAR'])
            ->assertSessionHas('warning', 'La carga no corresponde a un origen histórico.');

        $this->assertDatabaseHas('import_batch', ['batch_id' => $batchId]);
    }

    #[DataProvider('nonTerminalStatuses')]
    public function test_non_terminal_status_cannot_be_deleted(ImportStatus $status): void
    {
        $admin = User::factory()->admin()->create();
        $batchId = $this->createDeletableBatch('BBVA', ['estado' => $status->value]);

        $this->actingAs($admin)
            ->delete(route('imports.destroy', $batchId), ['confirmation' => 'ELIMINAR'])
            ->assertSessionHas('warning', 'La carga debe estar en un estado terminal para poder eliminarse.');

        $this->assertDatabaseHas('import_batch', ['batch_id' => $batchId]);
    }

    #[DataProvider('portfolioEntities')]
    public function test_deletion_removes_only_target_batch_from_every_entity_table(string $entity): void
    {
        $admin = User::factory()->admin()->create(['name' => 'Administradora KP']);
        $batchId = $this->createDeletableBatch($entity, [
            'filas_archivo' => 20,
            'filas_insertadas' => 18,
            'filas_error' => 2,
        ]);
        $otherBatchId = $this->createDeletableBatch($entity);
        $this->seedEntityTables($entity, $batchId, $otherBatchId);
        DB::connection('sqlite')->table('import_error')->insert([
            ['batch_id' => $batchId, 'numero_fila' => 2, 'error' => 'Error objetivo', 'created_at' => now('UTC')],
            ['batch_id' => $otherBatchId, 'numero_fila' => 3, 'error' => 'Error ajeno', 'created_at' => now('UTC')],
        ]);
        $path = (string) $this->batchRow($batchId)->archivo_ruta;
        Storage::disk('imports')->put($path, 'archivo privado');

        $this->actingAs($admin)
            ->delete(route('imports.destroy', $batchId), ['confirmation' => 'ELIMINAR'])
            ->assertRedirect(route('imports.index'))
            ->assertSessionHas('status', "Carga #{$batchId} eliminada correctamente.");

        foreach (config("imports.deletion.entity_tables.{$entity}") as $table) {
            $this->assertDatabaseMissing($table, ['batch_id' => $batchId]);
            $this->assertDatabaseHas($table, ['batch_id' => $otherBatchId]);
        }
        $this->assertDatabaseMissing('import_batch', ['batch_id' => $batchId]);
        $this->assertDatabaseMissing('import_error', ['batch_id' => $batchId]);
        $this->assertDatabaseHas('import_batch', ['batch_id' => $otherBatchId]);
        $this->assertDatabaseHas('import_error', ['batch_id' => $otherBatchId]);
        Storage::disk('imports')->assertMissing($path);
        $this->assertDatabaseHas('import_deletion_log', [
            'batch_id_original' => $batchId,
            'entidad' => $entity,
            'deleted_by_user_id' => $admin->id,
            'deleted_by_name' => 'Administradora KP',
            'file_deleted' => 1,
            'filas_archivo' => 20,
            'filas_insertadas' => 18,
            'filas_error' => 2,
        ]);
    }

    public function test_database_failure_rolls_back_and_keeps_private_file(): void
    {
        $admin = User::factory()->admin()->create();
        $batchId = $this->createDeletableBatch('BBVA');
        $this->seedEntityTables('BBVA', $batchId);
        $path = (string) $this->batchRow($batchId)->archivo_ruta;
        Storage::disk('imports')->put($path, 'archivo privado');
        DB::connection('sqlite')->unprepared(<<<SQL
            CREATE TRIGGER fail_portfolio_deletion
            BEFORE DELETE ON cartera_operaciones
            WHEN OLD.batch_id = {$batchId}
            BEGIN
                SELECT RAISE(ABORT, 'fallo simulado');
            END;
        SQL);

        $this->actingAs($admin)
            ->delete(route('imports.destroy', $batchId), ['confirmation' => 'ELIMINAR'])
            ->assertSessionHas('warning', 'No fue posible eliminar la carga. No se realizó ningún cambio.');

        $this->assertDatabaseHas('import_batch', ['batch_id' => $batchId]);
        $this->assertDatabaseHas('cartera_operaciones', ['batch_id' => $batchId]);
        $this->assertDatabaseCount('import_deletion_log', 0);
        Storage::disk('imports')->assertExists($path);
    }

    public function test_locked_batch_is_revalidated_if_status_changes_before_transaction(): void
    {
        $admin = User::factory()->admin()->create();
        $batchId = $this->createDeletableBatch('BBVA');
        $statusChanged = false;
        DB::connection('sqlite')->listen(function (QueryExecuted $query) use (&$statusChanged, $batchId): void {
            if ($statusChanged || ! str_contains($query->sql, 'select * from "import_batch"')) {
                return;
            }

            $statusChanged = true;
            DB::connection('sqlite')->table('import_batch')->where('batch_id', $batchId)->update([
                'estado' => ImportStatus::Processing->value,
            ]);
        });

        $this->actingAs($admin)
            ->delete(route('imports.destroy', $batchId), ['confirmation' => 'ELIMINAR'])
            ->assertSessionHas('warning', 'La carga debe estar en un estado terminal para poder eliminarse.');

        $this->assertTrue($statusChanged);
        $this->assertDatabaseHas('import_batch', [
            'batch_id' => $batchId,
            'estado' => ImportStatus::Processing->value,
        ]);
        $this->assertDatabaseCount('import_deletion_log', 0);
    }

    public function test_missing_private_file_does_not_prevent_database_cleanup(): void
    {
        $admin = User::factory()->admin()->create();
        $batchId = $this->createDeletableBatch('COMPARTAMOS');
        $this->seedEntityTables('COMPARTAMOS', $batchId);

        $this->actingAs($admin)
            ->delete(route('imports.destroy', $batchId), ['confirmation' => 'ELIMINAR'])
            ->assertRedirect(route('imports.index'))
            ->assertSessionHas('warning', "Carga #{$batchId} eliminada. El archivo privado ya no estaba disponible.");

        $this->assertDatabaseMissing('import_batch', ['batch_id' => $batchId]);
        $this->assertDatabaseHas('import_deletion_log', [
            'batch_id_original' => $batchId,
            'file_deleted' => 0,
            'warning' => 'El archivo privado ya no estaba disponible.',
        ]);
    }

    public function test_valid_stored_path_takes_precedence_over_internal_filename_fallback(): void
    {
        $admin = User::factory()->admin()->create();
        $batchId = $this->createDeletableBatch('COMPARTAMOS', [
            'archivo_interno' => '../metadata-interna-invalida.xlsx',
            'archivo_ruta' => '2026/10/18/ruta-registrada.xlsx',
        ]);
        Storage::disk('imports')->put('2026/10/18/ruta-registrada.xlsx', 'archivo privado');

        $this->actingAs($admin)
            ->delete(route('imports.destroy', $batchId), ['confirmation' => 'ELIMINAR'])
            ->assertRedirect(route('imports.index'))
            ->assertSessionHas('status', "Carga #{$batchId} eliminada correctamente.");

        Storage::disk('imports')->assertMissing('2026/10/18/ruta-registrada.xlsx');
    }

    #[DataProvider('emptyStoredPaths')]
    public function test_internal_filename_reconstructs_and_deletes_the_private_file_when_stored_path_is_empty(
        ?string $storedPath,
    ): void {
        $admin = User::factory()->admin()->create();
        $batchId = $this->createDeletableBatch('COMPARTAMOS', [
            'archivo_interno' => '6b43852a-19ea-40a8-b849-75ac09ac8fb6.xlsx',
            'archivo_ruta' => $storedPath,
            'fecha_inicio' => '2026-10-16 03:30:00',
        ]);
        $resolvedPath = "2026/10/{$batchId}/6b43852a-19ea-40a8-b849-75ac09ac8fb6.xlsx";
        Storage::disk('imports')->put($resolvedPath, 'archivo privado');

        $this->actingAs($admin)
            ->delete(route('imports.destroy', $batchId), ['confirmation' => 'ELIMINAR'])
            ->assertRedirect(route('imports.index'))
            ->assertSessionHas('status', "Carga #{$batchId} eliminada correctamente.");

        Storage::disk('imports')->assertMissing($resolvedPath);
        $this->assertDatabaseHas('import_deletion_log', [
            'batch_id_original' => $batchId,
            'file_deleted' => 1,
            'warning' => null,
        ]);
    }

    public function test_path_is_resolved_from_the_locked_batch_instead_of_the_initial_snapshot(): void
    {
        $admin = User::factory()->admin()->create();
        $batchId = $this->createDeletableBatch('BBVA', [
            'archivo_ruta' => '2026/10/18/snapshot.xlsx',
        ]);
        $lockedPath = '2026/10/18/batch-bloqueado.xlsx';
        Storage::disk('imports')->put('2026/10/18/snapshot.xlsx', 'conservar');
        Storage::disk('imports')->put($lockedPath, 'eliminar');
        $metadataChanged = false;
        DB::connection('sqlite')->listen(function (QueryExecuted $query) use (&$metadataChanged, $batchId, $lockedPath): void {
            if ($metadataChanged || ! str_contains($query->sql, 'select * from "import_batch"')) {
                return;
            }

            $metadataChanged = true;
            DB::connection('sqlite')->table('import_batch')->where('batch_id', $batchId)->update([
                'archivo_ruta' => $lockedPath,
            ]);
        });

        $this->actingAs($admin)
            ->delete(route('imports.destroy', $batchId), ['confirmation' => 'ELIMINAR'])
            ->assertRedirect(route('imports.index'));

        $this->assertTrue($metadataChanged);
        Storage::disk('imports')->assertExists('2026/10/18/snapshot.xlsx');
        Storage::disk('imports')->assertMissing($lockedPath);
    }

    public function test_physical_deletion_failure_keeps_database_deletion_and_records_warning(): void
    {
        $admin = User::factory()->admin()->create();
        $batchId = $this->createDeletableBatch('BBVA');
        $path = (string) $this->batchRow($batchId)->archivo_ruta;
        $this->partialMock(ImportFileService::class, function (MockInterface $mock) use ($path): void {
            $mock->shouldReceive('exists')->once()->with($path)->andReturnTrue();
            $mock->shouldReceive('delete')->once()->with($path)->andThrow(
                new \RuntimeException('fallo simulado del filesystem'),
            );
        });

        $this->actingAs($admin)
            ->delete(route('imports.destroy', $batchId), ['confirmation' => 'ELIMINAR'])
            ->assertRedirect(route('imports.index'))
            ->assertSessionHas('warning', "Carga #{$batchId} eliminada. El archivo físico requiere limpieza manual.");

        $this->assertDatabaseMissing('import_batch', ['batch_id' => $batchId]);
        $this->assertDatabaseHas('import_deletion_log', [
            'batch_id_original' => $batchId,
            'file_deleted' => 0,
            'warning' => 'El archivo físico requiere limpieza manual.',
        ]);
    }

    public function test_path_traversal_metadata_is_rejected_without_touching_database_or_files(): void
    {
        $admin = User::factory()->admin()->create();
        $batchId = $this->createDeletableBatch('COMPARTAMOS', [
            'archivo_ruta' => '../fuera.xlsx',
        ]);
        Storage::disk('imports')->put('fuera.xlsx', 'no eliminar');

        $this->actingAs($admin)
            ->delete(route('imports.destroy', $batchId), ['confirmation' => 'ELIMINAR'])
            ->assertSessionHas('warning', 'La ubicación privada registrada para el archivo no es válida.');

        $this->assertDatabaseHas('import_batch', ['batch_id' => $batchId]);
        $this->assertDatabaseCount('import_deletion_log', 0);
        Storage::disk('imports')->assertExists('fuera.xlsx');
    }

    #[DataProvider('absoluteStoredPaths')]
    public function test_absolute_stored_path_is_rejected(string $storedPath): void
    {
        $admin = User::factory()->admin()->create();
        $batchId = $this->createDeletableBatch('COMPARTAMOS', [
            'archivo_ruta' => $storedPath,
        ]);

        $this->actingAs($admin)
            ->delete(route('imports.destroy', $batchId), ['confirmation' => 'ELIMINAR'])
            ->assertSessionHas('warning', 'La ubicación privada registrada para el archivo no es válida.');

        $this->assertDatabaseHas('import_batch', ['batch_id' => $batchId]);
        $this->assertDatabaseCount('import_deletion_log', 0);
    }

    public function test_path_traversal_cannot_delete_a_file_from_another_private_disk(): void
    {
        Storage::fake('local');
        $admin = User::factory()->admin()->create();
        $batchId = $this->createDeletableBatch('COMPARTAMOS', [
            'archivo_ruta' => '../documento-privado.txt',
        ]);
        Storage::disk('local')->put('documento-privado.txt', 'conservar');

        $this->actingAs($admin)
            ->delete(route('imports.destroy', $batchId), ['confirmation' => 'ELIMINAR'])
            ->assertSessionHas('warning', 'La ubicación privada registrada para el archivo no es válida.');

        Storage::disk('local')->assertExists('documento-privado.txt');
        $this->assertDatabaseHas('import_batch', ['batch_id' => $batchId]);
    }

    /**
     * @param  array<string, mixed>  $overrides
     */
    private function createDeletableBatch(string $entity, array $overrides = []): int
    {
        return $this->createBatch(array_merge([
            'tipo' => ImportType::Portfolio->value,
            'entidad' => $entity,
            'perfil_version' => '1',
            'origen' => ImportOrigin::Historical->value,
            'estado' => ImportStatus::CompletedWithErrors->value,
            'archivo_original' => strtolower($entity).'.xlsx',
            'archivo_ruta' => '2026/10/18/'.strtolower($entity).'.xlsx',
        ], $overrides));
    }

    private function seedEntityTables(string $entity, int $batchId, ?int $otherBatchId = null): void
    {
        foreach (config("imports.deletion.entity_tables.{$entity}") as $table) {
            DB::connection('sqlite')->table($table)->insert([
                'batch_id' => $batchId,
                'payload' => 'objetivo',
            ]);
            if ($otherBatchId !== null) {
                DB::connection('sqlite')->table($table)->insert([
                    'batch_id' => $otherBatchId,
                    'payload' => 'conservar',
                ]);
            }
        }
    }

    /**
     * @return array<string, array{string}>
     */
    public static function nonAdminUsers(): array
    {
        return [
            'operador' => ['operator'],
            'lectura' => ['readOnly'],
        ];
    }

    /**
     * @return array<string, array{ImportStatus}>
     */
    public static function nonTerminalStatuses(): array
    {
        return [
            'pendiente' => [ImportStatus::Pending],
            'procesando' => [ImportStatus::Processing],
            'validando' => [ImportStatus::Validating],
        ];
    }

    /**
     * @return array<string, array{string}>
     */
    public static function portfolioEntities(): array
    {
        return [
            'BBVA' => ['BBVA'],
            'Caja Arequipa' => ['CAJA_AREQUIPA'],
            'Compartamos' => ['COMPARTAMOS'],
            'Financiera Confianza' => ['CONFIANZA'],
            'Wandoo' => ['WANDOO'],
        ];
    }

    /**
     * @return array<string, array{string|null}>
     */
    public static function emptyStoredPaths(): array
    {
        return [
            'cadena vacía' => [''],
            'nulo' => [null],
        ];
    }

    /**
     * @return array<string, array{string}>
     */
    public static function absoluteStoredPaths(): array
    {
        return [
            'Unix' => ['/var/private/import.xlsx'],
            'Windows' => ['C:\\private\\import.xlsx'],
        ];
    }
}
