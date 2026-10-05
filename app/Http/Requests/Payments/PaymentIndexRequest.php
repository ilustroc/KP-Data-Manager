<?php

namespace App\Http\Requests\Payments;

use Illuminate\Contracts\Validation\ValidationRule;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

class PaymentIndexRequest extends FormRequest
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
            'fecha_desde' => ['nullable', 'date_format:Y-m-d'],
            'fecha_hasta' => [
                'nullable',
                'date_format:Y-m-d',
                Rule::when($this->filled('fecha_desde'), ['after_or_equal:fecha_desde']),
            ],
            'documento' => ['nullable', 'string', 'max:30'],
            'operacion' => ['nullable', 'string', 'max:100'],
            'recaudo' => ['nullable', 'string', 'max:50'],
            'monto_min' => ['nullable', 'numeric', 'decimal:0,2', 'min:0'],
            'monto_max' => [
                'nullable',
                'numeric',
                'decimal:0,2',
                'min:0',
                Rule::when($this->filled('monto_min'), ['gte:monto_min']),
            ],
            'estado' => ['nullable', Rule::in(['todos', 'identificados', 'sin_identificar'])],
            'per_page' => ['nullable', 'integer', Rule::in(config('payments.pagination.allowed'))],
        ];
    }

    /**
     * @return array<string, string>
     */
    public function messages(): array
    {
        return [
            'fecha_desde.date_format' => 'La fecha desde debe ser una fecha válida.',
            'fecha_hasta.date_format' => 'La fecha hasta debe ser una fecha válida.',
            'fecha_hasta.after_or_equal' => 'La fecha hasta debe ser igual o posterior a la fecha desde.',
            'documento.max' => 'El documento no puede exceder 30 caracteres.',
            'operacion.max' => 'La operación no puede exceder 100 caracteres.',
            'recaudo.max' => 'El recaudo no puede exceder 50 caracteres.',
            'monto_min.numeric' => 'El monto mínimo debe ser un número válido.',
            'monto_min.decimal' => 'El monto mínimo puede tener como máximo dos decimales.',
            'monto_min.min' => 'El monto mínimo debe ser mayor o igual a cero.',
            'monto_max.numeric' => 'El monto máximo debe ser un número válido.',
            'monto_max.decimal' => 'El monto máximo puede tener como máximo dos decimales.',
            'monto_max.min' => 'El monto máximo debe ser mayor o igual a cero.',
            'monto_max.gte' => 'El monto máximo debe ser mayor o igual al monto mínimo.',
            'estado.in' => 'El estado seleccionado no es válido.',
            'per_page.in' => 'La cantidad por página debe ser 25, 50 o 100.',
        ];
    }
}
