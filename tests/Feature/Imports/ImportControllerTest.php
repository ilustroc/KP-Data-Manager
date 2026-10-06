<?php

namespace Tests\Feature\Imports;

use App\ImportOrigin;
use App\ImportStatus;
use App\ImportType;
use App\Jobs\ProcessImportBatch;
use App\Models\User;
use App\UserRole;
use Illuminate\Contracts\Pagination\Paginator;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Queue;
use Illuminate\Support\Facades\Storage;
use PHPUnit\Framework\Attributes\DataProvider;
use RuntimeException;

class ImportControllerTest extends ImportFeatureTestCase
{
    public function test_unauthenticated_user_cannot_access_imports(): void
    {
        $this->get(route('imports.index'))->assertRedirectToRoute('login');
        $this->get(route('imports.create'))->assertRedirectToRoute('login');
    }

    #[DataProvider('operatorRoles')]
    public function test_authorized_role_can_create_import(UserRole $role): void
    {
        Queue::fake([ProcessImportBatch::class]);
        Storage::fake('imports');
        $user = User::factory()->create(['role' => $role]);

        $response = $this->actingAs($user)->post(route('imports.store'), [
            'tipo' => ImportType::Payments->value,
            'origen' => ImportOrigin::Daily->value,
            'archivo' => $this->validCsv(),
        ]);

        $batchId = (int) DB::connection('sqlite')->table('import_batch')->value('batch_id');
        $response
            ->assertRedirectToRoute('imports.show', $batchId)
            ->assertSessionHas('status', "La carga #{$batchId} fue registrada y enviada a procesamiento.");

        Queue::assertPushed(ProcessImportBatch::class, fn (ProcessImportBatch $job): bool => $job->batchId === $batchId);
    }

    public function test_read_only_user_cannot_create_import(): void
    {
        Storage::fake('imports');
        $user = User::factory()->readOnly()->create();

        $this->actingAs($user)->post(route('imports.store'), [
            'tipo' => ImportType::Payments->value,
            'origen' => ImportOrigin::Daily->value,
            'archivo' => $this->validCsv(),
        ])->assertForbidden();

        $this->assertDatabaseCount('import_batch', 0);
    }

    public function test_inactive_user_is_blocked(): void
    {
        $user = User::factory()->inactive()->create();

        $this->actingAs($user)
            ->get(route('imports.index'))
            ->assertRedirectToRoute('login')
            ->assertSessionHasErrors('email');
    }

    public function test_valid_csv_is_registered_in_private_storage_with_complete_metadata(): void
    {
        Queue::fake([ProcessImportBatch::class]);
        Storage::fake('imports');
        Storage::fake('public');
        $contents = "FECHA,DOCUMENTO\n2026-10-01,003241\n";
        $user = User::factory()->operator()->create();

        $this->actingAs($user)->post(route('imports.store'), [
            'tipo' => ImportType::Payments->value,
            'origen' => ImportOrigin::Manual->value,
            'archivo' => $this->validCsv('Pagos Octubre.csv', $contents),
        ])->assertRedirect();

        $batch = DB::connection('sqlite')->table('import_batch')->firstOrFail();

        $this->assertSame(ImportStatus::Pending->value, $batch->estado);
        $this->assertSame('Pagos Octubre.csv', $batch->archivo_original);
        $this->assertSame(strlen($contents), $batch->archivo_tamano);
        $this->assertSame(hash('sha256', $contents), $batch->archivo_sha256);
        $this->assertSame('csv', $batch->archivo_extension);
        $this->assertSame('user:'.$user->id, $batch->usuario);
        $this->assertNotSame('Pagos Octubre.csv', $batch->archivo_interno);
        $this->assertStringEndsWith('.csv', $batch->archivo_interno);
        Storage::disk('imports')->assertExists($batch->archivo_ruta);
        Storage::disk('public')->assertMissing($batch->archivo_ruta);
        Queue::assertPushed(ProcessImportBatch::class, 1);
    }

    public function test_valid_xlsx_is_registered(): void
    {
        Queue::fake([ProcessImportBatch::class]);
        Storage::fake('imports');
        $user = User::factory()->admin()->create();

        $this->actingAs($user)->post(route('imports.store'), [
            'tipo' => ImportType::Payments->value,
            'origen' => ImportOrigin::Historical->value,
            'archivo' => $this->validXlsx(),
        ])->assertRedirect();

        $this->assertDatabaseHas('import_batch', [
            'archivo_original' => 'pagos.xlsx',
            'archivo_extension' => 'xlsx',
            'estado' => ImportStatus::Pending->value,
        ]);
    }

    public function test_disallowed_extension_fails_validation(): void
    {
        Storage::fake('imports');
        $user = User::factory()->operator()->create();

        $this->actingAs($user)
            ->from(route('imports.create'))
            ->post(route('imports.store'), [
                'tipo' => ImportType::Payments->value,
                'origen' => ImportOrigin::Daily->value,
                'archivo' => $this->validCsv('malware.exe'),
            ])
            ->assertInvalid('archivo');

        $this->assertDatabaseCount('import_batch', 0);
    }

    public function test_fake_file_renamed_as_xlsx_is_rejected(): void
    {
        Storage::fake('imports');
        $user = User::factory()->operator()->create();

        $this->actingAs($user)
            ->from(route('imports.create'))
            ->post(route('imports.store'), [
                'tipo' => ImportType::Payments->value,
                'origen' => ImportOrigin::Daily->value,
                'archivo' => $this->validCsv('falso.xlsx', 'MZ executable content'),
            ])
            ->assertInvalid('archivo');

        $this->assertDatabaseCount('import_batch', 0);
    }

    public function test_identical_file_is_not_registered_twice(): void
    {
        Queue::fake([ProcessImportBatch::class]);
        Storage::fake('imports');
        $user = User::factory()->operator()->create();
        $payload = [
            'tipo' => ImportType::Payments->value,
            'origen' => ImportOrigin::Daily->value,
            'archivo' => $this->validCsv(contents: 'same bytes'),
        ];

        $this->actingAs($user)->post(route('imports.store'), $payload)->assertRedirect();
        $batchId = (int) DB::connection('sqlite')->table('import_batch')->value('batch_id');

        $this->actingAs($user)
            ->from(route('imports.create'))
            ->post(route('imports.store'), array_merge($payload, [
                'archivo' => $this->validCsv('otro-nombre.csv', 'same bytes'),
            ]))
            ->assertInvalid(['archivo' => "Este archivo ya fue registrado en la carga #{$batchId}."]);

        $this->assertDatabaseCount('import_batch', 1);
        Queue::assertPushed(ProcessImportBatch::class, 1);
    }

    public function test_history_is_paginated_and_ordered_by_latest_batch(): void
    {
        $user = User::factory()->readOnly()->create();

        for ($index = 1; $index <= 26; $index++) {
            $this->createBatch(['archivo_original' => "batch-{$index}.csv"]);
        }

        $this->actingAs($user)
            ->get(route('imports.index'))
            ->assertOk()
            ->assertViewHas('batches', function (Paginator $batches): bool {
                $items = $batches->items();

                return $batches->perPage() === 25
                    && count($items) === 25
                    && $items[0]->batch_id === 26
                    && $batches->nextPageUrl() !== null;
            });
    }

    public function test_history_filters_are_applied_in_sql(): void
    {
        $user = User::factory()->readOnly()->create();
        $targetBatchId = $this->createBatch([
            'origen' => ImportOrigin::Historical->value,
            'estado' => ImportStatus::Error->value,
            'archivo_original' => 'objetivo.csv',
            'usuario' => 'user:42',
            'fecha_inicio' => '2026-10-05 03:00:00',
        ]);
        $this->createBatch(['archivo_original' => 'otro.csv']);

        $this->actingAs($user)->get(route('imports.index', [
            'batch_id' => $targetBatchId,
            'tipo' => ImportType::Payments->value,
            'origen' => ImportOrigin::Historical->value,
            'estado' => ImportStatus::Error->value,
            'fecha_desde' => '2026-10-04',
            'fecha_hasta' => '2026-10-04',
            'nombre_archivo' => 'objetivo',
            'usuario' => 'user:42',
        ]))
            ->assertSeeText('objetivo.csv')
            ->assertDontSeeText('otro.csv');
    }

    public function test_existing_batch_detail_includes_errors_and_lima_time(): void
    {
        Storage::fake('imports');
        $user = User::factory()->readOnly()->create();
        $batchId = $this->createBatch();
        Storage::disk('imports')->put('2026/10/1/internal.csv', 'contents');
        DB::connection('sqlite')->table('import_error')->insert([
            'batch_id' => $batchId,
            'numero_fila' => 7,
            'campo' => 'MONTO',
            'valor' => 'abc',
            'error' => 'Monto inválido',
            'created_at' => '2026-10-05 03:35:00',
        ]);

        $this->actingAs($user)
            ->get(route('imports.show', $batchId))
            ->assertOk()
            ->assertSeeText("Carga #{$batchId}")
            ->assertSeeText('04/10/2026 22:30:00')
            ->assertSeeText('Monto inválido');
    }

    public function test_unknown_batch_returns_404(): void
    {
        Storage::fake('imports');
        $user = User::factory()->readOnly()->create();

        $this->actingAs($user)->get(route('imports.show', 999999))->assertNotFound();
    }

    public function test_no_delete_endpoint_exists(): void
    {
        $user = User::factory()->admin()->create();
        $batchId = $this->createBatch();

        $this->actingAs($user)->delete('/cargas/'.$batchId)->assertMethodNotAllowed();
    }

    public function test_registration_persists_utc_and_presents_lima_time(): void
    {
        Queue::fake([ProcessImportBatch::class]);
        Storage::fake('imports');
        Carbon::setTestNow(Carbon::parse('2026-10-05 03:30:00', 'UTC'));
        $user = User::factory()->operator()->create();

        $this->actingAs($user)->post(route('imports.store'), [
            'tipo' => ImportType::Payments->value,
            'origen' => ImportOrigin::Daily->value,
            'archivo' => $this->validCsv(),
        ]);

        $batch = DB::connection('sqlite')->table('import_batch')->firstOrFail();
        $this->assertSame('2026-10-05 03:30:00', $batch->fecha_inicio);

        $this->actingAs($user)
            ->get(route('imports.show', $batch->batch_id))
            ->assertSeeText('04/10/2026 22:30:00');
    }

    public function test_registering_file_does_not_modify_bronze_guard_table(): void
    {
        Queue::fake([ProcessImportBatch::class]);
        Storage::fake('imports');
        DB::connection('sqlite')->table('raw_pagos_import_guard')->insert([
            'raw_id' => 100,
            'DOCUMENTO' => '3241',
        ]);
        $before = DB::connection('sqlite')->table('raw_pagos_import_guard')->get()->toArray();
        $user = User::factory()->operator()->create();

        $this->actingAs($user)->post(route('imports.store'), [
            'tipo' => ImportType::Payments->value,
            'origen' => ImportOrigin::Daily->value,
            'archivo' => $this->validCsv(),
        ]);

        $after = DB::connection('sqlite')->table('raw_pagos_import_guard')->get()->toArray();
        $this->assertEquals($before, $after);
    }

    public function test_queue_dispatch_failure_keeps_pending_batch_and_private_file(): void
    {
        Queue::fake([ProcessImportBatch::class]);
        Queue::beforePushing(function (): never {
            throw new RuntimeException('simulated queue failure');
        });
        Storage::fake('imports');
        $user = User::factory()->operator()->create();

        $response = $this->actingAs($user)->post(route('imports.store'), [
            'tipo' => ImportType::Payments->value,
            'origen' => ImportOrigin::Daily->value,
            'archivo' => $this->validCsv(),
        ]);

        $batch = DB::connection('sqlite')->table('import_batch')->firstOrFail();

        $response
            ->assertRedirectToRoute('imports.show', $batch->batch_id)
            ->assertSessionHas('warning', "La carga #{$batch->batch_id} fue registrada, pero no fue posible enviarla a procesamiento.");
        $this->assertSame(ImportStatus::Pending->value, $batch->estado);
        Storage::disk('imports')->assertExists($batch->archivo_ruta);
        Queue::assertNothingPushed();
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
}
