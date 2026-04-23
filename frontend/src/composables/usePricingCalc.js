import { computed } from 'vue'

/**
 * 定价表计算 composable (纯函数 computed)
 *
 * @param {Ref} itemRef - reactive ref of { weight_kg, length_cm, width_cm, height_cm, purchase_cost }
 * @param {Ref} platformRef - reactive ref of { price_rub, price_rmb, discount_pct } (wb_cross_fbs 行)
 * @param {Ref} paramsRef - reactive ref of { rate_rub_cny, rate_usd_cny, order_fee_threshold_kg, order_fee_light, order_fee_heavy, withdrawal_rate }
 * @param {Ref} wbCrossRateRef - reactive ref of { id, rate, product_name, category } | null (当前 item 选的 WB 跨境佣金率对象)
 * @param {Ref} shippingRatesRef - reactive ref of Array<{density_min, density_max, price_usd}> (默认模板的 rates)
 *
 * 返回 computed<{
 *   volume, density, frontPriceRub, headPriceUsd, headFee, orderFee, tailFee,
 *   commissionRatePct, commission, withdrawalFee, profit, profitRatePct
 * }>
 *
 * null = 不可计算 (显示为 '-')
 */
export function usePricingCalc(itemRef, platformRef, paramsRef, wbCrossRateRef, shippingRatesRef) {
  return computed(() => {
    const item = itemRef.value || {}
    const pl = platformRef.value || {}
    const P = paramsRef.value || {}
    const rateEntry = wbCrossRateRef.value || null
    const sr = shippingRatesRef.value || []

    const weight = Number(item.weight_kg) || 0
    const L = Number(item.length_cm) || 0
    const W = Number(item.width_cm) || 0
    const H = Number(item.height_cm) || 0
    const purchase = Number(item.purchase_cost) || 0
    const priceRub = Number(pl.price_rub) || 0
    const priceRmb = Number(pl.price_rmb) || 0
    const discount = Number(pl.discount_pct) || 0

    // 体积 m³ (4 位小数), 密度 kg/m³ (2 位小数)
    const volumeRaw = (L * W * H) / 1_000_000
    const volume = volumeRaw > 0 ? Number(volumeRaw.toFixed(4)) : null
    const density = volume && weight > 0 ? Number((weight / volume).toFixed(2)) : null

    // 前台售价 RUB
    const frontPriceRub = priceRub * (1 - discount / 100)

    // 头程单价: 按 density 匹配 shippingRates
    let headPriceUsd = null
    if (density != null && sr.length > 0) {
      const sorted = [...sr].sort((a, b) => a.density_min - b.density_min)
      if (density < sorted[0].density_min) {
        headPriceUsd = sorted[0].price_usd  // 超小 → 第一档
      } else {
        const match = sorted.find(r => density >= r.density_min && density < r.density_max)
        if (match) {
          headPriceUsd = match.price_usd
        } else {
          headPriceUsd = sorted[sorted.length - 1].price_usd  // 超大 → 最后一档
        }
      }
    }

    // 头程费用 RMB
    const headFee = headPriceUsd != null && P.rate_usd_cny
      ? weight * headPriceUsd * P.rate_usd_cny
      : null

    // 订单处理费 (weight < threshold → light; else heavy)
    const orderFee = P.order_fee_threshold_kg != null && P.order_fee_light != null && P.order_fee_heavy != null
      ? (weight < P.order_fee_threshold_kg ? P.order_fee_light : P.order_fee_heavy)
      : null

    // 尾程运费 RMB = L×W×H/1000 + 4
    const tailFee = (L > 0 && W > 0 && H > 0) ? (L * W * H / 1000 + 4) : null

    // 佣金率 (佣金表存小数,如 0.11); rateEntry 由调用方按 id 单独 fetch 传入
    const commissionRateDecimal = rateEntry ? Number(rateEntry.rate) : null
    const commissionRatePct = commissionRateDecimal != null ? commissionRateDecimal * 100 : null

    // 佣金 RMB
    const commission = commissionRateDecimal != null ? priceRmb * commissionRateDecimal : null

    // 提现手续费 RMB = (price_rmb - 尾程 - 佣金) × withdrawal_rate
    const withdrawalFee = (tailFee != null && commission != null && P.withdrawal_rate != null)
      ? (priceRmb - tailFee - commission) * P.withdrawal_rate
      : null

    // 利润 RMB
    let profit = null
    if (headFee != null && orderFee != null && tailFee != null && commission != null && withdrawalFee != null) {
      profit = priceRmb - (purchase + headFee + orderFee + tailFee + commission + withdrawalFee)
    }

    // 利润率 %
    const profitRatePct = (profit != null && priceRmb > 0) ? (profit / priceRmb) * 100 : null

    return {
      volume, density, frontPriceRub,
      headPriceUsd, headFee,
      orderFee, tailFee,
      commissionRatePct, commission, withdrawalFee,
      profit, profitRatePct,
    }
  })
}
