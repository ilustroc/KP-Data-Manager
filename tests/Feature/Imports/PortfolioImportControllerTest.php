<?php

namespace Tests\Feature\Imports;

use App\FinancialEntity;
use App\ImportOrigin;
use App\ImportStatus;
use App\ImportType;
use App\Jobs\ProcessImportBatch;
use App\Models\User;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Queue;
use Illuminate\Support\Facades\Storage;

class PortfolioImportControllerTest extends ImportFeatureTestCase
{
    public function test_create_form_offers_portfolio_and_only_enables_bbva(): void
    {
        $user = User::factory()->operator()->create();

        $this->actingAs($user)
            ->get(route('imports.create'))
            ->assertSeeText('Cartera')
            ->assertSeeText('BBVA')
            ->assertSeeText('Caja Arequipa · Próximamente');
    }

    public function test_portfolio_requires_financial_entity(): void
    {
        Storage::fake('imports');
        $user = User::factory()->operator()->create();

        $this->actingAs($user)
            ->from(route('imports.create'))
            ->post(route('imports.store'), [
                'tipo' => ImportType::Portfolio->value,
                'origen' => ImportOrigin::Historical->value,
                'archivo' => $this->validCsv('cartera.csv'),
            ])
            ->assertInvalid(['entidad' => 'Selecciona la entidad financiera de la cartera.']);

        $this->assertDatabaseCount('import_batch', 0);
    }

    public function test_unknown_financial_entity_is_rejected(): void
    {
        Storage::fake('imports');
        $user = User::factory()->operator()->create();

        $this->actingAs($user)
            ->from(route('imports.create'))
            ->post(route('imports.store'), [
                'tipo' => ImportType::Portfolio->value,
                'entidad' => 'ENTIDAD_DESCONOCIDA',
                'origen' => ImportOrigin::Historical->value,
                'archivo' => $this->validCsv('cartera.csv'),
            ])
            ->assertInvalid(['entidad' => 'La entidad financiera seleccionada no es válida.']);

        $this->assertDatabaseCount('import_batch', 0);
    }

    public function test_entity_without_profile_cannot_be_registered(): void
    {
        Storage::fake('imports');
        $user = User::factory()->operator()->create();

        $this->actingAs($user)
            ->from(route('imports.create'))
            ->post(route('imports.store'), [
                'tipo' => ImportType::Portfolio->value,
                'entidad' => FinancialEntity::Wandoo->value,
                'origen' => ImportOrigin::Historical->value,
                'archivo' => $this->validCsv('wandoo.csv'),
            ])
            ->assertInvalid(['entidad' => 'La entidad seleccionada aún no está disponible para procesamiento.']);

        $this->assertDatabaseCount('import_batch', 0);
    }

    public function test_valid_bbva_portfolio_is_registered_with_profile_and_dispatched(): void
    {
        Queue::fake([ProcessImportBatch::class]);
        Storage::fake('imports');
        $user = User::factory()->operator()->create();

        $response = $this->actingAs($user)->post(route('imports.store'), [
            'tipo' => ImportType::Portfolio->value,
            'entidad' => FinancialEntity::Bbva->value,
            'origen' => ImportOrigin::Historical->value,
            'archivo' => $this->validCsv('BBVA_OCTUBRE.csv'),
        ]);

        $batch = DB::connection('sqlite')->table('import_batch')->firstOrFail();
        $response->assertRedirectToRoute('imports.show', $batch->batch_id);
        $this->assertSame(ImportType::Portfolio->value, $batch->tipo);
        $this->assertSame(FinancialEntity::Bbva->value, $batch->entidad);
        $this->assertSame('1', $batch->perfil_version);
        $this->assertSame(ImportStatus::Pending->value, $batch->estado);
        Queue::assertPushed(
            ProcessImportBatch::class,
            fn (ProcessImportBatch $job): bool => $job->batchId === (int) $batch->batch_id,
        );
    }

    public function test_history_and_detail_show_bbva_without_exposing_profile_version(): void
    {
        $user = User::factory()->readOnly()->create();
        $batchId = $this->createBatch([
            'tipo' => ImportType::Portfolio->value,
            'entidad' => FinancialEntity::Bbva->value,
            'perfil_version' => '1',
            'archivo_original' => 'BBVA_OCTUBRE.xlsx',
        ]);

        $this->actingAs($user)
            ->get(route('imports.index'))
            ->assertSeeText('Cartera / BBVA')
            ->assertDontSeeText('perfil_version');

        $this->actingAs($user)
            ->get(route('imports.show', $batchId))
            ->assertSeeText('Entidad')
            ->assertSeeText('BBVA')
            ->assertDontSeeText('perfil_version');
    }
}
