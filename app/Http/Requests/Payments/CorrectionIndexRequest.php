<?php

namespace App\Http\Requests\Payments;

use Illuminate\Contracts\Validation\ValidationRule;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

class CorrectionIndexRequest extends FormRequest
{
    /**
     * Determine if the user is authorized to make this request.
     */
    public function authorize(): bool
    {
        return $this->user()?->can('view-data') ?? false;
    }

    /**
     * Get the validation rules that apply to the request.
     *
     * @return array<string, ValidationRule|array<mixed>|string>
     */
    public function rules(): array
    {
        return [
            'fecha_cambio_desde' => ['nullable', 'date_format:Y-m-d'],
            'fecha_cambio_hasta' => [
                'nullable',
                'date_format:Y-m-d',
                Rule::when($this->filled('fecha_cambio_desde'), ['after_or_equal:fecha_cambio_desde']),
            ],
            'documento' => ['nullable', 'string', 'max:30'],
            'usuario' => ['nullable', 'string', 'max:100'],
            'raw_pago_id' => ['nullable', 'integer', 'min:1'],
            'per_page' => ['nullable', 'integer', Rule::in(config('payments.pagination.allowed'))],
        ];
    }

    /**
     * @return array<string, string>
     */
    public function messages(): array
    {
        return [
            'fecha_cambio_desde.date_format' => 'La fecha de cambio desde debe ser una fecha válida.',
            'fecha_cambio_hasta.date_format' => 'La fecha de cambio hasta debe ser una fecha válida.',
            'fecha_cambio_hasta.after_or_equal' => 'La fecha de cambio hasta debe ser igual o posterior a la fecha desde.',
            'documento.max' => 'El documento no puede exceder 30 caracteres.',
            'usuario.max' => 'El usuario no puede exceder 100 caracteres.',
            'raw_pago_id.integer' => 'El Raw ID debe ser un número entero.',
            'raw_pago_id.min' => 'El Raw ID debe ser mayor que cero.',
            'per_page.in' => 'La cantidad por página debe ser 25, 50 o 100.',
        ];
    }
}
