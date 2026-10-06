<?php

namespace App\Http\Requests\Imports;

use App\FinancialEntity;
use App\ImportOrigin;
use App\ImportStatus;
use App\ImportType;
use Illuminate\Contracts\Validation\ValidationRule;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

class ImportIndexRequest extends FormRequest
{
    public function authorize(): bool
    {
        return $this->user()?->can('view-data') ?? false;
    }

    /**
     * @return array<string, ValidationRule|array<mixed>|string>
     */
    public function rules(): array
    {
        return [
            'batch_id' => ['nullable', 'integer', 'min:1'],
            'tipo' => ['nullable', Rule::enum(ImportType::class)],
            'entidad' => ['nullable', Rule::enum(FinancialEntity::class)],
            'origen' => ['nullable', Rule::enum(ImportOrigin::class)],
            'estado' => ['nullable', Rule::enum(ImportStatus::class)],
            'fecha_desde' => ['nullable', 'date_format:Y-m-d'],
            'fecha_hasta' => [
                'nullable',
                'date_format:Y-m-d',
                Rule::when($this->filled('fecha_desde'), ['after_or_equal:fecha_desde']),
            ],
            'nombre_archivo' => ['nullable', 'string', 'max:255'],
            'usuario' => ['nullable', 'string', 'max:100'],
            'per_page' => ['nullable', 'integer', Rule::in(config('imports.pagination.allowed'))],
        ];
    }

    /**
     * @return array<string, string>
     */
    public function messages(): array
    {
        return [
            'batch_id.integer' => 'El número de carga debe ser un número entero.',
            'batch_id.min' => 'El número de carga debe ser mayor que cero.',
            'tipo.enum' => 'El tipo seleccionado no es válido.',
            'entidad.enum' => 'La entidad financiera seleccionada no es válida.',
            'origen.enum' => 'El origen seleccionado no es válido.',
            'estado.enum' => 'El estado seleccionado no es válido.',
            'fecha_desde.date_format' => 'La fecha desde debe ser una fecha válida.',
            'fecha_hasta.date_format' => 'La fecha hasta debe ser una fecha válida.',
            'fecha_hasta.after_or_equal' => 'La fecha hasta debe ser igual o posterior a la fecha desde.',
            'nombre_archivo.max' => 'El nombre de archivo no puede exceder 255 caracteres.',
            'usuario.max' => 'El usuario no puede exceder 100 caracteres.',
            'per_page.in' => 'La cantidad por página debe ser 25, 50 o 100.',
        ];
    }
}
