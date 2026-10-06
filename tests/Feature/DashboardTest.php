<?php

namespace Tests\Feature;

use App\ImportStatus;
use App\Models\User;
use App\UserRole;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Foundation\Testing\LazilyRefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use PHPUnit\Framework\Attributes\DataProvider;
use Tests\TestCase;

class DashboardTest extends TestCase
{
    use LazilyRefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();

        $this->withoutVite();
        config([
            'imports.connection' => 'sqlite',
            'imports.table' => 'import_batch',
        ]);

        Schema::connection('sqlite')->dropIfExists('import_batch');
        Schema::connection('sqlite')->create('import_batch', function (Blueprint $table): void {
            $table->id('batch_id');
            $table->string('archivo');
            $table->string('archivo_original')->nullable();
            $table->dateTime('fecha_inicio');
            $table->string('estado', 30);
            $table->unsignedBigInteger('filas_insertadas')->default(0);
            $table->unsignedBigInteger('filas_error')->default(0);
            $table->string('usuario', 100)->nullable();
        });
    }

    public function test_guest_is_redirected_to_login(): void
    {
        $this->get(route('dashboard'))->assertRedirectToRoute('login');
    }

    #[DataProvider('activeRoles')]
    public function test_active_role_can_view_administrative_layout(UserRole $role): void
    {
        $user = User::factory()->create(['role' => $role]);

        $response = $this->actingAs($user)->get(route('dashboard'));

        $response
            ->assertViewIs('dashboard.index')
            ->assertSeeText('Dashboard')
            ->assertSee($role->label());
    }

    public function test_dashboard_shows_real_operational_summary_without_roadmap_content(): void
    {
        $this->travelTo('2026-10-06 15:00:00');
        $user = User::factory()->operator()->create(['name' => 'Jesús Gabriel Garcia Palacios']);
        $this->createImport([
            'archivo_original' => 'pagos-diarios.csv',
            'fecha_inicio' => '2026-10-06 12:00:00',
            'estado' => ImportStatus::Completed->value,
            'filas_insertadas' => 73,
            'usuario' => 'user:'.$user->id,
        ]);
        $this->createImport([
            'archivo_original' => 'pagos-observados.xlsx',
            'fecha_inicio' => '2026-10-06 13:00:00',
            'estado' => ImportStatus::CompletedWithErrors->value,
            'filas_insertadas' => 304,
            'filas_error' => 115,
            'usuario' => 'user:'.$user->id,
        ]);
        $this->createImport([
            'archivo_original' => 'pagos-pendientes.csv',
            'fecha_inicio' => '2026-10-06 14:00:00',
            'estado' => ImportStatus::Pending->value,
            'usuario' => 'user:'.$user->id,
        ]);
        $this->createImport([
            'archivo_original' => 'carga-anterior.csv',
            'fecha_inicio' => '2026-10-06 04:59:59',
            'estado' => ImportStatus::Completed->value,
            'filas_insertadas' => 999,
            'usuario' => 'user:'.$user->id,
        ]);

        $response = $this->actingAs($user)->get(route('dashboard'));

        $response
            ->assertSeeText('Buenos días, Jesús')
            ->assertSeeText('Cargas hoy')
            ->assertSeeText('Filas cargadas hoy')
            ->assertSeeText('pagos-pendientes.csv')
            ->assertDontSeeText('Fase 1')
            ->assertDontSeeText('Indicadores pendientes')
            ->assertDontSeeText('Silver')
            ->assertViewHas('summary', [
                'cargas_hoy' => 3,
                'filas_cargadas_hoy' => 377,
                'con_observaciones' => 1,
                'en_proceso' => 1,
            ]);
    }

    public function test_dashboard_escapes_user_name(): void
    {
        $dangerousName = "Jesús <script>alert('xss')</script>";
        $user = User::factory()->create(['name' => $dangerousName]);

        $response = $this->actingAs($user)->get(route('dashboard'));

        $response
            ->assertSee($dangerousName)
            ->assertDontSee($dangerousName, false);
    }

    /**
     * @return array<string, array{UserRole}>
     */
    public static function activeRoles(): array
    {
        return [
            'administrador' => [UserRole::Admin],
            'operador' => [UserRole::Operator],
            'lectura' => [UserRole::ReadOnly],
        ];
    }

    /**
     * @param  array<string, mixed>  $overrides
     */
    private function createImport(array $overrides = []): void
    {
        DB::connection('sqlite')->table('import_batch')->insert(array_merge([
            'archivo' => 'pagos.csv',
            'archivo_original' => 'pagos.csv',
            'fecha_inicio' => '2026-10-06 12:00:00',
            'estado' => ImportStatus::Completed->value,
            'filas_insertadas' => 0,
            'filas_error' => 0,
            'usuario' => 'cli:PC',
        ], $overrides));
    }
}
